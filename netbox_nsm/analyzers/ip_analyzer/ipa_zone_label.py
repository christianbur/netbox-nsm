"""Resolve Security Panel zone/label refs for IP Analyzer cell-tree rows."""

from __future__ import annotations

from typing import Any

from django.contrib.contenttypes.models import ContentType

from netbox_nsm.core.display_utils import get_display_template_map, render_object_display

__all__ = (
    "attach_ipa_cell_zone_label_refs",
    "resolve_ipa_label_refs",
    "resolve_ipa_zone_label_refs",
    "resolve_ipa_zone_refs",
)


def _role_for_linked_object(linked) -> str | None:
    cot = getattr(linked, "custom_object_type", None)
    if cot is None:
        return None
    from netbox_nsm.type_metadata.roles import resolve_role_for_cot

    return resolve_role_for_cot(cot)


def _display_ref(linked, *, tmpl_map, inherited: bool = False, inherited_from: str = "") -> dict[str, Any]:
    lct = ContentType.objects.get_for_model(linked)
    url = None
    if hasattr(linked, "get_absolute_url"):
        try:
            url = linked.get_absolute_url()
        except Exception:
            url = None
    name = render_object_display(linked, lct.pk, tmpl_map)
    ref: dict[str, Any] = {"name": name, "url": url}
    if inherited:
        ref["inherited"] = True
        if inherited_from:
            ref["inherited_from"] = inherited_from
    return ref


def _direct_refs_for_roles(obj, *, roles: set[str], tmpl_map, include_found_on: bool = False) -> list[dict[str, Any]]:
    from netbox_nsm.security.links.object_link_service import iter_links_for_object

    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for link, direction in iter_links_for_object(obj):
        linked = link.security_object if direction == "fwd" else link.netbox_object
        if linked is None:
            continue
        role = _role_for_linked_object(linked)
        if role not in roles:
            continue
        url = None
        if hasattr(linked, "get_absolute_url"):
            try:
                url = linked.get_absolute_url()
            except Exception:
                url = None
        dedupe = (role, url or str(getattr(linked, "pk", "")))
        if dedupe in seen:
            continue
        seen.add(dedupe)
        lct = ContentType.objects.get_for_model(linked)
        ref_dict = {
            "name": render_object_display(linked, lct.pk, tmpl_map),
            "url": url,
        }
        if include_found_on:
            # Add info about which object (host/interface) has the label/zone
            obj_display = str(obj)
            if hasattr(obj, "get_absolute_url"):
                try:
                    ref_dict["found_on_object"] = obj
                    ref_dict["found_on_object_display"] = obj_display
                except Exception:
                    pass
        refs.append(ref_dict)
    refs.sort(key=lambda row: (row.get("name") or "").lower())
    return refs


def _prefix_display(ancestor) -> str:
    prefix = getattr(ancestor, "prefix", None)
    if prefix is not None:
        return str(prefix)
    return str(ancestor)


def _safe_display_template_map():
    """Best-effort display template map for analyzer rendering.

    Some SimpleTestCase-based analyzer tests disallow DB access. In that
    context we fall back to an empty template map instead of raising.
    """
    try:
        return get_display_template_map()
    except Exception:
        return {}


def resolve_ipa_zone_refs(obj, *, tmpl_map=None) -> list[dict[str, Any]]:
    """Return zone display refs for *obj* (direct, else all inherited from prefixes).
    
    For each zone, includes 'found_on_prefix' showing where it was linked (for inherited)
    or 'found_on_object' showing the directly linked object.
    """
    if obj is None:
        return []
    if tmpl_map is None:
        tmpl_map = _safe_display_template_map()

    # Check for direct zones on the object itself
    direct = _direct_refs_for_roles(obj, roles={"zone"}, tmpl_map=tmpl_map, include_found_on=True)
    if direct:
        return direct

    from ipam.models import IPAddress, IPRange, Prefix

    if not isinstance(obj, (IPAddress, IPRange, Prefix)):
        return []

    from netbox_nsm.addresses.ipam_inheritance import iter_inherited_nsm_links

    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    try:
        inherited_links = list(iter_inherited_nsm_links(obj))
    except Exception:
        inherited_links = []

    # Collect ALL zones from all ancestor prefixes (not just first)
    for inherited in inherited_links:
        linked = inherited.linked
        if linked is None:
            continue
        if _role_for_linked_object(linked) != "zone":
            continue
        
        ancestor_prefix = _prefix_display(inherited.ancestor)
        ref = _display_ref(
            linked,
            tmpl_map=tmpl_map,
            inherited=True,
            inherited_from=ancestor_prefix,
        )
        # Add info about which prefix the zone was found on
        ref["found_on_prefix"] = ancestor_prefix
        
        dedupe = (ref.get("name") or "", ref.get("url") or "")
        if dedupe in seen:
            continue
        seen.add(dedupe)
        refs.append(ref)
    
    refs.sort(key=lambda row: (row.get("name") or "").lower())
    return refs


def resolve_ipa_label_refs(obj, *, tmpl_map=None) -> list[dict[str, Any]]:
    """Return label display refs assigned directly to *obj* (no prefix inheritance).
    
    Includes 'found_on_object' info showing which object (host/interface) has the label.
    """
    if obj is None:
        return []
    if tmpl_map is None:
        tmpl_map = _safe_display_template_map()
    return _direct_refs_for_roles(obj, roles={"label"}, tmpl_map=tmpl_map, include_found_on=True)


def resolve_ipa_zone_label_refs(obj, *, tmpl_map=None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if tmpl_map is None:
        tmpl_map = _safe_display_template_map()
    return resolve_ipa_zone_refs(obj, tmpl_map=tmpl_map), resolve_ipa_label_refs(
        obj, tmpl_map=tmpl_map
    )


def attach_ipa_cell_zone_label_refs(nodes, obj_by_key=None):
    """Attach ``zone_refs`` / ``label_refs`` to visible cell-tree rows."""
    from netbox_nsm.analyzers.ip_analyzer import ipa_object_tree as tree

    tmpl_map = _safe_display_template_map()
    prefix_cache: dict[str, Any] = {}

    def _ipam_target_for_node(node, obj):
        ipam_obj = tree._ipa_cell_tree_ipam_object_for_node(node, obj=obj)
        if ipam_obj is not None:
            return ipam_obj
        cidr = (node.get("prefix_display_cidr") or (node.get("ip_ref") or {}).get("str") or "").strip()
        if not cidr or "/" not in cidr:
            return None
        if cidr not in prefix_cache:
            try:
                prefix_cache[cidr] = tree._hub._lookup_ipam_prefix_from_ip_ref({"str": cidr})
            except Exception:
                prefix_cache[cidr] = None
        return prefix_cache[cidr]

    for node in nodes or []:
        if node.get("layer") == "ipam_prefix":
            attach_ipa_cell_zone_label_refs(node.get("children") or [], obj_by_key)
            continue
        if tree._ipa_tree_node_is_structural(node):
            attach_ipa_cell_zone_label_refs(node.get("children") or [], obj_by_key)
            continue

        # Lazy mode should stay responsive on large trees: resolve refs only for
        # directly selected rows.
        try:
            if tree.ipa_lazy_load_enabled() and not (
                node.get("is_cell_direct") or node.get("in_cell")
            ):
                attach_ipa_cell_zone_label_refs(node.get("children") or [], obj_by_key)
                continue
        except Exception:
            pass

        key = tree._ipa_object_tree_node_key(node)
        obj = obj_by_key.get(key) if key and obj_by_key else None
        ipam_obj = _ipam_target_for_node(node, obj)
        target = ipam_obj or obj
        if target is not None:
            zones, labels = resolve_ipa_zone_label_refs(target, tmpl_map=tmpl_map)
            if zones:
                node["zone_refs"] = zones
            if labels:
                node["label_refs"] = labels

        attach_ipa_cell_zone_label_refs(node.get("children") or [], obj_by_key)
