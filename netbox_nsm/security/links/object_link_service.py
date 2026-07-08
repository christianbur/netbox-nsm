"""Security Panel assignments via ``nsm_object_link`` COT (source of truth)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from django.contrib.contenttypes.models import ContentType

from netbox_nsm.type_metadata.config import is_linkable_content_type
from netbox_nsm.security.links.cot_link_schema import (
    ObjectLinkSchema,
    get_object_link_schema,
    read_link_endpoints,
)
from netbox_nsm.security.links.link_propagation import (
    CotObjectLinkPropagationChoices,
    LinkPropagationChoices,
    cot_propagation_to_native,
)

__all__ = (
    "NSM_OBJECT_LINK_SLUG",
    "LINK_TYPE_POLICY",
    "ObjectLinkRecord",
    "classify_link_endpoints",
    "create_or_update_links",
    "delete_link",
    "direct_nsm_type_keys_for_object",
    "find_link_between",
    "get_link_by_pk",
    "get_object_link_model",
    "is_policy_link_instance",
    "iter_links_for_object",
    "iter_links_on_container",
    "iter_links_stored_on_netbox_object",
    "iter_policy_links_for_object",
    "link_name_for_endpoints",
    "object_link_permission",
    "update_link",
)

NSM_OBJECT_LINK_SLUG = "nsm_object_link"  # bundle schema slug only; runtime lookup uses link_table metadata
LINK_TYPE_POLICY = "policy"

_INHERIT_IPAM_COT = (
    CotObjectLinkPropagationChoices.INHERIT_IPAM,
    CotObjectLinkPropagationChoices.INHERIT_IPAM_STOP,
)
_INHERIT_GROUP_COT = (
    CotObjectLinkPropagationChoices.INHERIT_GROUP,
    CotObjectLinkPropagationChoices.INHERIT_GROUP_STOP,
)


def get_object_link_model():
    """Return the dynamic model for the link-table COT, or ``None``."""
    schema = get_object_link_schema()
    if schema is None:
        return None
    try:
        return schema.cot.get_model()
    except Exception:
        return None


def _require_object_link_schema() -> ObjectLinkSchema:
    schema = get_object_link_schema()
    if schema is None:
        raise RuntimeError("link-table COT is not deployed")
    return schema


def _read_row_endpoints(schema: ObjectLinkSchema, instance):
    return read_link_endpoints(schema, instance)


def object_link_permission(action: str) -> str | None:
    """Return ``netbox_custom_objects`` permission codename for the link-table COT."""
    model = get_object_link_model()
    if model is None:
        return None
    return f"netbox_custom_objects.{action}_{model._meta.model_name}"


def is_policy_link_instance(instance) -> bool:
    """True for policy links: legacy ``link_type=policy`` rows and policy-only rows."""
    link_type = getattr(instance, "link_type", None)
    if link_type is not None:
        normalized = str(link_type).strip()
        if normalized and normalized != LINK_TYPE_POLICY:
            return False

    schema = get_object_link_schema()
    if schema is None:
        return True

    _, policy = _read_row_endpoints(schema, instance)
    return policy is not None


def _poly_filter_param(field_name: str, content_type: ContentType) -> str:
    return f"{field_name}_{content_type.app_label}_{content_type.model}"


def _filter_instances_by_object_ref(model, field_name: str, obj) -> list:
    """Return COT rows whose polymorphic *field_name* points at *obj*."""
    ct = ContentType.objects.get_for_model(obj)
    try:
        from utilities.filtersets import get_filterset_class

        param = _poly_filter_param(field_name, ct)
        filterset = get_filterset_class(model)(
            {param: [obj.pk]},
            model.objects.all(),
        )
        return list(filterset.qs.order_by("created", "pk"))
    except Exception:
        pass

    matches = []
    ct_id = ct.pk
    obj_id = obj.pk
    for instance in model.objects.all().order_by("created", "pk"):
        related = getattr(instance, field_name, None)
        if related is None:
            continue
        try:
            related_ct = ContentType.objects.get_for_model(related)
        except Exception:
            continue
        if related_ct.pk == ct_id and related.pk == obj_id:
            matches.append(instance)
    return matches


def classify_link_endpoints(object_a, object_b):
    """
    Map legacy ObjectLink endpoints to ``(netbox_object, security_object)``.

    Policy side is identified via TypeConfig linkable types;
    if both or neither match, *object_a* is treated as netbox host (legacy ObjectLink A).
    """
    ct_a = ContentType.objects.get_for_model(object_a)
    ct_b = ContentType.objects.get_for_model(object_b)
    a_policy = is_linkable_content_type(ct_a.pk)
    b_policy = is_linkable_content_type(ct_b.pk)
    if a_policy and not b_policy:
        return object_b, object_a
    return object_a, object_b


def link_name_for_endpoints(netbox_obj, policy_obj) -> str:
    return f"{netbox_obj} → {policy_obj}"[:200]


@dataclass
class ObjectLinkRecord:
    """Adapter: one ``nsm_object_link`` COT row."""

    pk: int
    instance: object | None
    comment: str
    propagation: str
    propagate_stop_on_own: bool
    netbox_object: object | None = None
    security_object: object | None = None

    @classmethod
    def from_instance(cls, instance, schema: ObjectLinkSchema | None = None) -> ObjectLinkRecord:
        if schema is None:
            schema = get_object_link_schema()
        netbox_object = None
        security_object = None
        if schema is not None:
            netbox_object, security_object = _read_row_endpoints(schema, instance)
        cot_value = getattr(
            instance,
            "propagation",
            CotObjectLinkPropagationChoices.DIRECT,
        )
        propagation, stop = cot_propagation_to_native(cot_value)
        return cls(
            pk=instance.pk,
            instance=instance,
            comment=(getattr(instance, "comment", None) or "").strip(),
            propagation=propagation,
            propagate_stop_on_own=stop,
            netbox_object=netbox_object,
            security_object=security_object,
        )

    @property
    def cot_propagation(self) -> str:
        if self.instance is not None:
            return getattr(
                self.instance,
                "propagation",
                CotObjectLinkPropagationChoices.DIRECT,
            )
        from netbox_nsm.security.links.link_propagation import native_propagation_to_cot

        return native_propagation_to_cot(self.propagation, self.propagate_stop_on_own)

    @property
    def object_a(self):
        return self.netbox_object

    @property
    def object_b(self):
        return self.security_object

    @property
    def object_a_type(self):
        obj = self.netbox_object
        return ContentType.objects.get_for_model(obj) if obj is not None else None

    @property
    def object_b_type(self):
        obj = self.security_object
        return ContentType.objects.get_for_model(obj) if obj is not None else None

    @property
    def object_a_id(self):
        obj = self.netbox_object
        return obj.pk if obj is not None else None

    @property
    def object_b_id(self):
        obj = self.security_object
        return obj.pk if obj is not None else None

    def get_propagation_display(self) -> str:
        from netbox_nsm.security.links.link_propagation import cot_propagation_display

        return cot_propagation_display(self.cot_propagation)

    def __str__(self) -> str:
        return f"{self.netbox_object} ↔ {self.security_object}"


def get_link_by_pk(pk: int) -> ObjectLinkRecord | None:
    model = get_object_link_model()
    if model is None:
        return None
    try:
        row = model.objects.get(pk=pk)
    except model.DoesNotExist:
        return None
    if not is_policy_link_instance(row):
        return None
    return ObjectLinkRecord.from_instance(row)


def find_link_between(object_a, object_b) -> ObjectLinkRecord | None:
    """Find assignment between page object *object_a* and linked row *object_b*."""
    if object_a is None or object_b is None:
        return None
    schema = get_object_link_schema()
    if schema is None:
        return None
    model = get_object_link_model()
    if model is None:
        return None

    netbox, policy = classify_link_endpoints(object_a, object_b)
    for row in _filter_instances_by_object_ref(model, schema.host_field, netbox):
        if not is_policy_link_instance(row):
            continue
        row_netbox, row_policy = _read_row_endpoints(schema, row)
        if row_policy is None:
            continue
        if row_policy.pk == policy.pk and ContentType.objects.get_for_model(
            row_policy
        ) == ContentType.objects.get_for_model(policy):
            return ObjectLinkRecord.from_instance(row, schema)
    return None


def iter_links_stored_on_netbox_object(netbox_obj) -> Iterator[ObjectLinkRecord]:
    """Yield links where ``netbox_object`` equals *netbox_obj* (assign host)."""
    for link, direction in iter_links_for_object(netbox_obj):
        if direction == "fwd":
            yield link


def iter_links_for_object(obj) -> Iterator[tuple[ObjectLinkRecord, str]]:
    """
    Yield ``(link, direction)`` for Security Panel display (policy links only).

    ``direction`` is ``fwd`` when *obj* is ``netbox_object`` (shows security_object),
    ``rev`` when *obj* is ``security_object`` (shows netbox_object).
    """
    yield from iter_policy_links_for_object(obj)


def iter_policy_links_for_object(obj) -> Iterator[tuple[ObjectLinkRecord, str]]:
    schema = get_object_link_schema()
    model = get_object_link_model()
    if schema is None or model is None or obj is None:
        return

    seen: set[int] = set()
    for row in _filter_instances_by_object_ref(model, schema.host_field, obj):
        if row.pk in seen or not is_policy_link_instance(row):
            continue
        seen.add(row.pk)
        yield ObjectLinkRecord.from_instance(row, schema), "fwd"

    for row in _filter_instances_by_object_ref(model, schema.security_field, obj):
        if row.pk in seen or not is_policy_link_instance(row):
            continue
        seen.add(row.pk)
        yield ObjectLinkRecord.from_instance(row, schema), "rev"


def iter_links_on_container(
    container_obj,
    *,
    inherit_mode: str,
) -> Iterator[ObjectLinkRecord]:
    """Yield inheriting links stored on *container_obj* (prefix, group, …)."""
    schema = get_object_link_schema()
    model = get_object_link_model()
    if schema is None or model is None:
        return

    if inherit_mode == LinkPropagationChoices.INHERIT_IPAM:
        allowed_cot = _INHERIT_IPAM_COT
    elif inherit_mode == LinkPropagationChoices.INHERIT_GROUP:
        allowed_cot = _INHERIT_GROUP_COT
    else:
        return

    for row in _filter_instances_by_object_ref(model, schema.host_field, container_obj):
        if not is_policy_link_instance(row):
            continue
        prop = getattr(row, "propagation", "")
        if prop not in allowed_cot:
            continue
        yield ObjectLinkRecord.from_instance(row, schema)


def direct_nsm_type_keys_for_object(obj, _ipam_ct=None) -> set[str]:
    """Type keys of objects directly linked to *obj* (panel inheritance dedupe)."""
    covered: set[str] = set()
    for link, direction in iter_links_for_object(obj):
        linked = link.security_object if direction == "fwd" else link.netbox_object
        if linked is None:
            continue
        lct = ContentType.objects.get_for_model(linked)
        covered.add(f"{lct.app_label}__{lct.model}")
    return covered


def create_or_update_links(
    netbox_obj,
    policy_obj,
    *,
    comment: str = "",
) -> tuple[ObjectLinkRecord, bool]:
    """Create or update one link-table row. Returns ``(link, created)``."""
    schema = _require_object_link_schema()
    model = get_object_link_model()
    if model is None:
        raise RuntimeError("link-table COT is not deployed")

    netbox_obj, policy_obj = classify_link_endpoints(netbox_obj, policy_obj)

    existing = find_link_between(netbox_obj, policy_obj)
    if existing is not None and existing.instance is not None:
        inst = existing.instance
        changed = False
        new_comment = comment or ""
        if (getattr(inst, "comment", None) or "") != new_comment:
            inst.comment = new_comment
            changed = True
        if changed:
            inst.save()
        return ObjectLinkRecord.from_instance(inst, schema), False

    inst = model.objects.create(
        name=link_name_for_endpoints(netbox_obj, policy_obj),
        **{
            schema.host_field: netbox_obj,
            schema.security_field: policy_obj,
            "comment": comment or "",
        },
    )
    return ObjectLinkRecord.from_instance(inst, schema), True


def update_link(
    link: ObjectLinkRecord,
    *,
    comment: str = "",
) -> ObjectLinkRecord:
    if link.instance is None:
        raise ValueError("Cannot update pseudo link record without instance")
    inst = link.instance
    inst.comment = comment or ""
    inst.save()
    return ObjectLinkRecord.from_instance(inst)


def delete_link(link: ObjectLinkRecord) -> None:
    if link.instance is None:
        raise ValueError("Cannot delete pseudo link record without instance")
    link.instance.delete()
