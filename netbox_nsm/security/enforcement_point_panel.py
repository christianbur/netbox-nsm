"""Security Panel enforcement-point section (host and interface rulebook context)."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from netbox_nsm.core.interface_parent import get_interface_parent_host
from netbox_nsm.security.links.object_link_service import (
    iter_enforcement_point_links_for_object,
    iter_enforcement_point_links_stored_on_object,
    iter_rulebook_links_for_object,
    object_link_permission,
)

__all__ = ("build_enforcement_point_panel",)


def _resolve_enforcement_point_context(obj):
    """Return (panel_host, iface) for Device/VM/VDC or Interface/VMInterface."""
    meta = getattr(obj, "_meta", None)
    label = getattr(meta, "label_lower", "") if meta is not None else ""
    if label in ("dcim.interface", "virtualization.vminterface"):
        host = get_interface_parent_host(obj)
        if host is None:
            return None, None
        return host, obj
    if label in (
        "dcim.device",
        "virtualization.virtualmachine",
        "dcim.virtualdevicecontext",
    ):
        return obj, None
    return None, None


def build_enforcement_point_panel(
    obj,
    *,
    request,
    panel_url,
    return_url: str,
) -> dict | None:
    """Return enforcement-point panel context for host or interface pages."""
    host, iface = _resolve_enforcement_point_context(obj)
    if host is None:
        return None

    delete_perm = object_link_permission("delete")
    can_delete = bool(
        request
        and request.user.is_authenticated
        and delete_perm
        and request.user.has_perm(delete_perm)
    )

    seen_slugs: set[str] = set()
    rulebooks: list[dict] = []

    def _rulebook_row(*, slug: str, rulebook, delete_url: str | None) -> dict:
        if rulebook is not None:
            return {
                "name": rulebook.name,
                "url": panel_url(rulebook.get_rules_tab_url()),
                "delete_url": delete_url,
            }
        from netbox_nsm.security.object_rules import build_rulebook_rules_tab_url

        return {
            "name": slug,
            "url": panel_url(build_rulebook_rules_tab_url(slug)),
            "delete_url": delete_url,
        }

    def _append_link(*, slug: str, rulebook, delete_pk: int | None) -> None:
        if not slug or slug in seen_slugs:
            return
        seen_slugs.add(slug)
        delete_url = None
        if can_delete and delete_pk is not None:
            delete_url = panel_url(
                reverse(
                    "plugins:netbox_nsm:enforcement_point_link_delete",
                    kwargs={"pk": delete_pk},
                )
                + f"?return_url={return_url}"
            )
        rulebooks.append(_rulebook_row(slug=slug, rulebook=rulebook, delete_url=delete_url))

    for ep_link in iter_enforcement_point_links_for_object(host):
        slug = (ep_link.rulebook_slug or "").strip()
        _append_link(slug=slug, rulebook=ep_link.rulebook, delete_pk=ep_link.pk)

    for rb_link in iter_rulebook_links_for_object(host):
        slug = (rb_link.rulebook_slug or "").strip()
        delete_url = None
        if can_delete:
            delete_url = panel_url(
                reverse(
                    "plugins:netbox_nsm:rulebook_link_delete",
                    kwargs={"pk": rb_link.pk},
                )
                + f"?return_url={return_url}"
            )
        if not slug or slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        rulebooks.append(_rulebook_row(slug=slug, rulebook=rb_link.rulebook, delete_url=delete_url))

    if iface is not None:
        for ep_link in iter_enforcement_point_links_stored_on_object(iface):
            slug = (ep_link.rulebook_slug or "").strip()
            _append_link(slug=slug, rulebook=ep_link.rulebook, delete_pk=ep_link.pk)

    if not rulebooks:
        return None

    rulebooks.sort(key=lambda row: row["name"].lower())

    add_url = None
    add_perm = object_link_permission("add")
    if request and add_perm and request.user.has_perm(add_perm):
        ct = ContentType.objects.get_for_model(host)
        add_url = panel_url(
            reverse("plugins:netbox_nsm:rulebook_link_assign")
            + f"?ct_id={ct.pk}&obj_id={host.pk}&return_url={return_url}"
        )

    return {
        "rulebooks": rulebooks,
        "count": len(rulebooks),
        "add_url": add_url,
        "is_interface": iface is not None,
    }
