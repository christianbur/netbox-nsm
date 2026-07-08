"""Prefill and labels for link-table Custom Object forms."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from netbox_nsm.security.links.cot_link_schema import (
    get_object_link_cot,
    is_link_table_cot,
)

__all__ = (
    "OBJECT_LINK_NETBOX_FIELD_LABEL",
    "OBJECT_LINK_SECURITY_FIELD_LABEL",
    "apply_object_link_add_prefill",
    "apply_object_link_form_labels",
    "is_object_link_add_form",
    "is_object_link_form",
    "object_link_field_prefix_for_ct",
    "sync_object_link_field_labels",
)

OBJECT_LINK_NETBOX_FIELD_LABEL = _("Netbox object")
OBJECT_LINK_SECURITY_FIELD_LABEL = _("Security object")

_OBJECT_LINK_FIELD_LABELS = {
    "netbox_object": OBJECT_LINK_NETBOX_FIELD_LABEL,
    "security_object": OBJECT_LINK_SECURITY_FIELD_LABEL,
}


def is_object_link_form(view) -> bool:
    """True when the view is adding or editing a link-table COT row."""
    obj = getattr(view, "object", None)
    if obj is None:
        return False
    cot = getattr(obj, "custom_object_type", None)
    return cot is not None and is_link_table_cot(cot)


def is_object_link_add_form(view) -> bool:
    """True when the view is adding a new link-table COT row."""
    obj = getattr(view, "object", None)
    if obj is None or obj.pk:
        return False
    cot = getattr(obj, "custom_object_type", None)
    return cot is not None and is_link_table_cot(cot)


def object_link_field_prefix_for_ct(content_type_id: int) -> str:
    """Return ``netbox_object`` (inventory) or ``security_object`` (security)."""
    from netbox_nsm.security.tab.eligibility import get_object_link_allowed_content_type_ids

    host_ids, security_ids = get_object_link_allowed_content_type_ids()
    if content_type_id in security_ids and content_type_id not in host_ids:
        return "security_object"
    return "netbox_object"


def _object_link_field_label(field_name: str):
    return _OBJECT_LINK_FIELD_LABELS.get(field_name)


def apply_object_link_form_labels(form) -> None:
    """Use Netbox / Security object headings on add and edit forms."""
    poly_pairs = getattr(form, "custom_object_type_poly_obj_pairs", None)
    if not poly_pairs:
        return
    for ct_sub, (obj_sub, _field_label) in list(poly_pairs.items()):
        field_name = ct_sub.split("__", 1)[0]
        label = _object_link_field_label(field_name)
        if label is None:
            continue
        text = str(label)
        poly_pairs[ct_sub] = (obj_sub, text)
        for sub_name in (ct_sub, obj_sub):
            field = form.fields.get(sub_name)
            if field is not None:
                field.label = label


def sync_object_link_field_labels() -> None:
    """Persist list/add column labels on the deployed link-table COT."""
    cot = get_object_link_cot()
    if cot is None:
        return

    for field_name, label in _OBJECT_LINK_FIELD_LABELS.items():
        cot.fields.filter(name=field_name).exclude(label=str(label)).update(label=str(label))


def _set_poly_prefill(initial: dict, field_prefix: str, ct_id, obj_id) -> None:
    ct_field = f"{field_prefix}__ct"
    obj_field = f"{field_prefix}__obj"
    if ct_field not in initial:
        initial[ct_field] = ct_id
    if obj_field not in initial:
        initial[obj_field] = obj_id


def _map_poly_object_prefill(
    initial: dict,
    *,
    ct_keys: tuple[str, ...],
    obj_keys: tuple[str, ...],
    field_prefix: str,
) -> None:
    ct_id = None
    for key in ct_keys:
        if key in initial:
            ct_id = initial.pop(key)
            break
    obj_id = None
    for key in obj_keys:
        if key in initial:
            obj_id = initial.pop(key)
            break
    if ct_id is None or obj_id is None:
        return
    _set_poly_prefill(initial, field_prefix, ct_id, obj_id)


def _map_routed_page_object_prefill(initial: dict) -> None:
    """Map generic ``ct_id`` / ``obj_id`` to netbox or security side from schema."""
    ct_id = initial.pop("ct_id", None)
    obj_id = initial.pop("obj_id", None)
    if ct_id is None or obj_id is None:
        if ct_id is not None:
            initial["ct_id"] = ct_id
        if obj_id is not None:
            initial["obj_id"] = obj_id
        return
    try:
        prefix = object_link_field_prefix_for_ct(int(ct_id))
    except (TypeError, ValueError):
        prefix = "netbox_object"
    _set_poly_prefill(initial, prefix, ct_id, obj_id)


def apply_object_link_add_prefill(cot, initial: dict) -> None:
    """Map friendly query params to polymorphic object sub-fields on add."""
    if not is_link_table_cot(cot):
        return

    if "comment" in initial and "comments" not in initial:
        initial["comments"] = initial.pop("comment")

    _map_routed_page_object_prefill(initial)
    _map_poly_object_prefill(
        initial,
        ct_keys=("object_a_type_id",),
        obj_keys=("object_a_id",),
        field_prefix="netbox_object",
    )
    _map_poly_object_prefill(
        initial,
        ct_keys=("object_b_type_id",),
        obj_keys=("object_b_id",),
        field_prefix="security_object",
    )

    initial.setdefault("status", "active")
