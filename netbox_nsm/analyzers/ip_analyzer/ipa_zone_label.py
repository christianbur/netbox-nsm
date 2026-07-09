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


def _direct_refs_for_roles(obj, *, roles: set[str], tmpl_map) -> list[dict[str, Any]]:
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
        refs.append(
            {
                "name": render_object_display(linked, lct.pk, tmpl_map),
                "url": url,
            }
        )
    refs.sort(key=lambda row: (row.get("name") or "").lower())
    return refs


def _prefix_display(ancestor) -> str:
    prefix = getattr(ancestor, "prefix", None)
    if prefix is not None:
        return str(prefix)
    return str(ancestor)


def resolve_ipa_zone_refs(obj, *, tmpl_map=None) -> list[dict[str, Any]]:
    """Return zone display refs for *obj* (direct, else inherited from prefixes)."""
    if obj is None:
        return []
    if tmpl_map is None:
        tmpl_map = get_display_template_map()

    direct = _direct_refs_for_roles(obj, roles={"zone"}, tmpl_map=tmpl_map)
    if direct:
        return direct

    from ipam.models import IPAddress, IPRange, Prefix

    if not isinstance(obj, (IPAddress, IPRange, Prefix)):
        return []

    from netbox_nsm.addresses.ipam_inheritance import iter_inherited_nsm_links

    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for inherited in iter_inherited_nsm_links(obj):
        linked = inherited.linked
        if linked is None:
            continue
        if _role_for_linked_object(linked) != "zone":
            continue
        ref = _display_ref(
            linked,
            tmpl_map=tmpl_map,
            inherited=True,
            inherited_from=_prefix_display(inherited.ancestor),
        )
        dedupe = (ref.get("name") or "", ref.get("url") or "")
        if dedupe in seen:
            continue
        seen.add(dedupe)
        refs.append(ref)
    refs.sort(key=lambda row: (row.get("name") or "").lower())
    return refs


def resolve_ipa_label_refs(obj, *, tmpl_map=None) -> list[dict[str, Any]]:
    """Return label display refs assigned directly to *obj* (no prefix inheritance)."""
    if obj is None:
        return []
    if tmpl_map is None:
        tmpl_map = get_display_template_map()
    return _direct_refs_for_roles(obj, roles={"label"}, tmpl_map=tmpl_map)


def resolve_ipa_zone_label_refs(obj, *, tmpl_map=None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if tmpl_map is None:
        tmpl_map = get_display_template_map()
    return resolve_ipa_zone_refs(obj, tmpl_map=tmpl_map), resolve_ipa_label_refs(
        obj, tmpl_map=tmpl_map
    )


def attach_ipa_cell_zone_label_refs(nodes, obj_by_key=None):
    """Attach ``zone_refs`` / ``label_refs`` to visible cell-tree rows."""
    from netbox_nsm.analyzers.ip_analyzer import ipa_object_tree as tree

    tmpl_map = get_display_template_map()
    for node in nodes or []:
        if node.get("layer") == "ipam_prefix":
            attach_ipa_cell_zone_label_refs(node.get("children") or [], obj_by_key)
            continue
        if tree._ipa_tree_node_is_structural(node):
            attach_ipa_cell_zone_label_refs(node.get("children") or [], obj_by_key)
            continue

        key = tree._ipa_object_tree_node_key(node)
        obj = obj_by_key.get(key) if key and obj_by_key else None
        ipam_obj = tree._ipa_cell_tree_ipam_object_for_node(node, obj=obj)
        target = ipam_obj or obj
        if target is not None:
            zones, labels = resolve_ipa_zone_label_refs(target, tmpl_map=tmpl_map)
            if zones:
                node["zone_refs"] = zones
            if labels:
                node["label_refs"] = labels

        attach_ipa_cell_zone_label_refs(node.get("children") or [], obj_by_key)
