"""Security Panel assignments via ``nsm_object_link`` COT (source of truth)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from django.contrib.contenttypes.models import ContentType

from netbox_nsm.type_metadata.config import is_linkable_content_type
from netbox_nsm.models.object_link import LinkPropagationChoices
from netbox_nsm.security.links.cot_link_schema import (
    ObjectLinkSchema,
    get_object_link_schema,
    read_link_endpoints,
)
from netbox_nsm.security.links.link_propagation import (
    CotObjectLinkPropagationChoices,
    cot_propagation_to_native,
)

__all__ = (
    "NSM_OBJECT_LINK_SLUG",
    "LINK_TYPE_POLICY",
    "LINK_TYPE_RULEBOOK",
    "LINK_TYPE_ENFORCEMENT_POINT",
    "ObjectLinkRecord",
    "RulebookLinkRecord",
    "EnforcementPointLinkRecord",
    "classify_link_endpoints",
    "create_or_update_links",
    "create_or_update_rulebook_link",
    "create_or_update_enforcement_point_link",
    "delete_link",
    "delete_rulebook_link",
    "delete_enforcement_point_link",
    "direct_nsm_type_keys_for_object",
    "find_link_between",
    "find_rulebook_link",
    "find_enforcement_point_host_link",
    "find_enforcement_point_iface_link",
    "get_link_by_pk",
    "get_object_link_model",
    "get_rulebook_link_by_pk",
    "get_enforcement_point_link_by_pk",
    "is_policy_link_instance",
    "is_rulebook_link_instance",
    "is_enforcement_point_host_link",
    "is_enforcement_point_iface_nsm_link",
    "is_enforcement_point_link_instance",
    "iter_links_for_object",
    "iter_links_on_container",
    "iter_links_stored_on_netbox_object",
    "iter_policy_links_for_object",
    "iter_rulebook_links_for_object",
    "iter_rulebook_links_for_slug",
    "iter_enforcement_point_links_for_object",
    "iter_enforcement_point_links_for_slug",
    "iter_enforcement_point_links_for_interface",
    "iter_enforcement_point_links_stored_on_object",
    "link_name_for_endpoints",
    "link_name_for_rulebook",
    "object_link_permission",
    "update_link",
)

NSM_OBJECT_LINK_SLUG = "nsm_object_link"  # bundle/schema slug; not used for runtime COT lookup
LINK_TYPE_POLICY = "policy"
LINK_TYPE_RULEBOOK = "rulebook"
LINK_TYPE_ENFORCEMENT_POINT = "enforcement_point"
LINK_TYPE_ENFORCEMENT_TARGET_LEGACY = "enforcement_target"

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


def _link_type_value(instance) -> str:
    value = getattr(instance, "link_type", None) or LINK_TYPE_POLICY
    return str(value).strip() or LINK_TYPE_POLICY


def is_policy_link_instance(instance) -> bool:
    return _link_type_value(instance) == LINK_TYPE_POLICY


def is_rulebook_link_instance(instance) -> bool:
    return _link_type_value(instance) == LINK_TYPE_RULEBOOK


def is_enforcement_point_link_instance(instance) -> bool:
    value = _link_type_value(instance)
    return value in (LINK_TYPE_ENFORCEMENT_POINT, LINK_TYPE_ENFORCEMENT_TARGET_LEGACY)


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
    Map legacy ObjectLink endpoints to ``(netbox_object, policy_object)``.

    Policy side is identified via TypeConfig linkable types; if both or
    neither match, *object_a* is treated as netbox host (legacy ObjectLink A).
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


def link_name_for_rulebook(netbox_obj, rulebook_slug: str) -> str:
    return f"{netbox_obj} → {rulebook_slug}"[:200]


def link_name_for_enforcement_point(
    netbox_obj,
    rulebook_slug: str,
    *,
    policy_obj=None,
) -> str:
    if policy_obj is None:
        return link_name_for_rulebook(netbox_obj, rulebook_slug)
    return f"{netbox_obj} → {policy_obj} @ {rulebook_slug}"[:200]


def _is_enforcement_point_host_object(obj) -> bool:
    from dcim.models import Device, VirtualDeviceContext
    from virtualization.models import VirtualMachine

    return isinstance(obj, (Device, VirtualMachine, VirtualDeviceContext))


def _is_enforcement_point_interface_object(obj) -> bool:
    from dcim.models import Interface
    from virtualization.models import VMInterface

    return isinstance(obj, (Interface, VMInterface))


def is_enforcement_point_host_link(link: EnforcementPointLinkRecord) -> bool:
    host = link.netbox_object
    return host is not None and link.policy_object is None and _is_enforcement_point_host_object(host)


def is_enforcement_point_iface_nsm_link(link: EnforcementPointLinkRecord) -> bool:
    iface = link.netbox_object
    return (
        iface is not None
        and link.policy_object is not None
        and _is_enforcement_point_interface_object(iface)
    )


@dataclass
class RulebookLinkRecord:
    """Adapter: one ``nsm_object_link`` row with ``link_type=rulebook``."""

    pk: int
    instance: object | None
    netbox_object: object | None
    rulebook_slug: str
    comment: str = ""

    @classmethod
    def from_instance(cls, instance, schema: ObjectLinkSchema | None = None) -> RulebookLinkRecord:
        if schema is None:
            schema = get_object_link_schema()
        netbox_object = None
        if schema is not None:
            netbox_object, _ = _read_row_endpoints(schema, instance)
        return cls(
            pk=instance.pk,
            instance=instance,
            netbox_object=netbox_object,
            rulebook_slug=(getattr(instance, "rulebook_slug", None) or "").strip(),
            comment=(getattr(instance, "comment", None) or "").strip(),
        )

    @property
    def rulebook(self):
        from netbox_nsm.rulebooks.registry import get_deployed_cot_rulebook
        from netbox_nsm.rulebooks.virtual_cot import build_virtual_cot_rulebook_row

        cot = get_deployed_cot_rulebook(self.rulebook_slug)
        if cot is None:
            return None
        return build_virtual_cot_rulebook_row(cot)


@dataclass
class EnforcementPointLinkRecord:
    """Adapter: one ``nsm_object_link`` row with ``link_type=enforcement_point``."""

    pk: int
    instance: object | None
    netbox_object: object | None
    policy_object: object | None
    rulebook_slug: str
    comment: str = ""

    @classmethod
    def from_instance(cls, instance, schema: ObjectLinkSchema | None = None) -> EnforcementPointLinkRecord:
        if schema is None:
            schema = get_object_link_schema()
        netbox_object = None
        policy_object = None
        if schema is not None:
            netbox_object, policy_object = _read_row_endpoints(schema, instance)
        return cls(
            pk=instance.pk,
            instance=instance,
            netbox_object=netbox_object,
            policy_object=policy_object,
            rulebook_slug=(getattr(instance, "rulebook_slug", None) or "").strip(),
            comment=(getattr(instance, "comment", None) or "").strip(),
        )

    @property
    def rulebook(self):
        from netbox_nsm.rulebooks.registry import get_deployed_cot_rulebook
        from netbox_nsm.rulebooks.virtual_cot import build_virtual_cot_rulebook_row

        cot = get_deployed_cot_rulebook(self.rulebook_slug)
        if cot is None:
            return None
        return build_virtual_cot_rulebook_row(cot)


@dataclass
class ObjectLinkRecord:
    """Adapter: one ``nsm_object_link`` COT row."""

    pk: int
    instance: object | None
    comment: str
    propagation: str
    propagate_stop_on_own: bool
    netbox_object: object | None = None
    policy_object: object | None = None

    @classmethod
    def from_instance(cls, instance, schema: ObjectLinkSchema | None = None) -> ObjectLinkRecord:
        if schema is None:
            schema = get_object_link_schema()
        netbox_object = None
        policy_object = None
        if schema is not None:
            netbox_object, policy_object = _read_row_endpoints(schema, instance)
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
            policy_object=policy_object,
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
        return self.policy_object

    @property
    def object_a_type(self):
        obj = self.netbox_object
        return ContentType.objects.get_for_model(obj) if obj is not None else None

    @property
    def object_b_type(self):
        obj = self.policy_object
        return ContentType.objects.get_for_model(obj) if obj is not None else None

    @property
    def object_a_id(self):
        obj = self.netbox_object
        return obj.pk if obj is not None else None

    @property
    def object_b_id(self):
        obj = self.policy_object
        return obj.pk if obj is not None else None

    def get_propagation_display(self) -> str:
        from netbox_nsm.security.links.link_propagation import cot_propagation_display

        return cot_propagation_display(self.cot_propagation)

    def __str__(self) -> str:
        return f"{self.netbox_object} ↔ {self.policy_object}"


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

    ``direction`` is ``fwd`` when *obj* is ``netbox_object`` (shows policy_object),
    ``rev`` when *obj* is ``policy_object`` (shows netbox_object).
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

    for row in _filter_instances_by_object_ref(model, schema.policy_field, obj):
        if row.pk in seen or not is_policy_link_instance(row):
            continue
        seen.add(row.pk)
        yield ObjectLinkRecord.from_instance(row, schema), "rev"


def iter_rulebook_links_for_object(obj) -> Iterator[RulebookLinkRecord]:
    """Yield rulebook assignment links stored on *obj*."""
    schema = get_object_link_schema()
    model = get_object_link_model()
    if schema is None or model is None or obj is None:
        return
    seen: set[int] = set()
    for row in _filter_instances_by_object_ref(model, schema.host_field, obj):
        if row.pk in seen or not is_rulebook_link_instance(row):
            continue
        seen.add(row.pk)
        yield RulebookLinkRecord.from_instance(row, schema)


def iter_rulebook_links_for_slug(rulebook_slug: str) -> Iterator[RulebookLinkRecord]:
    """Yield all hosts assigned to *rulebook_slug*."""
    model = get_object_link_model()
    if model is None or not rulebook_slug:
        return
    slug = rulebook_slug.strip()
    for row in model.objects.filter(rulebook_slug=slug).order_by("created", "pk"):
        if is_rulebook_link_instance(row):
            yield RulebookLinkRecord.from_instance(row)


def find_rulebook_link(netbox_obj, rulebook_slug: str) -> RulebookLinkRecord | None:
    schema = get_object_link_schema()
    model = get_object_link_model()
    if schema is None or model is None or netbox_obj is None or not rulebook_slug:
        return None
    for row in _filter_instances_by_object_ref(model, schema.host_field, netbox_obj):
        if not is_rulebook_link_instance(row):
            continue
        if (getattr(row, "rulebook_slug", None) or "").strip() == rulebook_slug.strip():
            return RulebookLinkRecord.from_instance(row, schema)
    return None


def get_rulebook_link_by_pk(pk: int) -> RulebookLinkRecord | None:
    model = get_object_link_model()
    if model is None:
        return None
    try:
        row = model.objects.get(pk=pk)
    except model.DoesNotExist:
        return None
    if not is_rulebook_link_instance(row):
        return None
    return RulebookLinkRecord.from_instance(row)


def create_or_update_rulebook_link(
    netbox_obj,
    rulebook_slug: str,
    *,
    comment: str = "",
) -> tuple[RulebookLinkRecord, bool]:
    schema = _require_object_link_schema()
    model = get_object_link_model()
    if model is None:
        raise RuntimeError("link-table COT is not deployed")
    slug = (rulebook_slug or "").strip()
    if not slug:
        raise ValueError("rulebook_slug is required")

    existing = find_rulebook_link(netbox_obj, slug)
    if existing is not None and existing.instance is not None:
        inst = existing.instance
        changed = False
        new_comment = comment or ""
        if (getattr(inst, "comment", None) or "") != new_comment:
            inst.comment = new_comment
            changed = True
        if changed:
            inst.save()
        return RulebookLinkRecord.from_instance(inst, schema), False

    inst = model.objects.create(
        name=link_name_for_rulebook(netbox_obj, slug),
        link_type=LINK_TYPE_RULEBOOK,
        **{
            schema.host_field: netbox_obj,
            "rulebook_slug": slug,
            "comment": comment or "",
        },
    )
    return RulebookLinkRecord.from_instance(inst, schema), True


def delete_rulebook_link(link: RulebookLinkRecord) -> None:
    if link.instance is None:
        raise ValueError("Cannot delete pseudo link record without instance")
    link.instance.delete()


def iter_enforcement_point_links_for_object(
    obj,
) -> Iterator[EnforcementPointLinkRecord]:
    """Yield enforcement-point host links stored on *obj*."""
    schema = get_object_link_schema()
    model = get_object_link_model()
    if schema is None or model is None or obj is None:
        return
    seen: set[int] = set()
    for row in _filter_instances_by_object_ref(model, schema.host_field, obj):
        if row.pk in seen or not is_enforcement_point_link_instance(row):
            continue
        link = EnforcementPointLinkRecord.from_instance(row, schema)
        if not is_enforcement_point_host_link(link):
            continue
        seen.add(row.pk)
        yield link


def iter_enforcement_point_links_stored_on_object(
    obj,
) -> Iterator[EnforcementPointLinkRecord]:
    """Yield enforcement-point rows stored on *obj* (host or interface netbox side)."""
    schema = get_object_link_schema()
    model = get_object_link_model()
    if schema is None or model is None or obj is None:
        return
    seen: set[int] = set()
    for row in _filter_instances_by_object_ref(model, schema.host_field, obj):
        if row.pk in seen or not is_enforcement_point_link_instance(row):
            continue
        seen.add(row.pk)
        yield EnforcementPointLinkRecord.from_instance(row, schema)


def iter_enforcement_point_links_for_slug(
    rulebook_slug: str,
) -> Iterator[EnforcementPointLinkRecord]:
    """Yield all enforcement-point links for *rulebook_slug*."""
    model = get_object_link_model()
    if model is None or not rulebook_slug:
        return
    slug = rulebook_slug.strip()
    for row in model.objects.filter(rulebook_slug=slug).order_by("created", "pk"):
        if is_enforcement_point_link_instance(row):
            yield EnforcementPointLinkRecord.from_instance(row)


def iter_enforcement_point_links_for_interface(
    iface,
    rulebook_slug: str,
) -> Iterator[EnforcementPointLinkRecord]:
    """Yield interface NSM enforcement-point links for *rulebook_slug*."""
    for link in iter_enforcement_point_links_for_slug(rulebook_slug):
        if link.netbox_object is None or link.policy_object is None:
            continue
        if not _is_enforcement_point_interface_object(link.netbox_object):
            continue
        if link.netbox_object.pk != iface.pk:
            continue
        if ContentType.objects.get_for_model(link.netbox_object) != ContentType.objects.get_for_model(iface):
            continue
        yield link


def find_enforcement_point_host_link(
    netbox_obj,
    rulebook_slug: str,
) -> EnforcementPointLinkRecord | None:
    schema = get_object_link_schema()
    model = get_object_link_model()
    if schema is None or model is None or netbox_obj is None or not rulebook_slug:
        return None
    for row in _filter_instances_by_object_ref(model, schema.host_field, netbox_obj):
        if not is_enforcement_point_link_instance(row):
            continue
        if (getattr(row, "rulebook_slug", None) or "").strip() != rulebook_slug.strip():
            continue
        _, row_policy = _read_row_endpoints(schema, row)
        if row_policy is not None:
            continue
        return EnforcementPointLinkRecord.from_instance(row, schema)
    return None


def find_enforcement_point_iface_link(
    iface,
    policy_obj,
    rulebook_slug: str,
) -> EnforcementPointLinkRecord | None:
    if iface is None or policy_obj is None or not rulebook_slug:
        return None
    policy_ct = ContentType.objects.get_for_model(policy_obj)
    for link in iter_enforcement_point_links_for_interface(iface, rulebook_slug):
        row_policy = link.policy_object
        if row_policy is None:
            continue
        if row_policy.pk == policy_obj.pk and ContentType.objects.get_for_model(row_policy) == policy_ct:
            return link
    return None


def get_enforcement_point_link_by_pk(pk: int) -> EnforcementPointLinkRecord | None:
    model = get_object_link_model()
    if model is None:
        return None
    try:
        row = model.objects.get(pk=pk)
    except model.DoesNotExist:
        return None
    if not is_enforcement_point_link_instance(row):
        return None
    return EnforcementPointLinkRecord.from_instance(row)


def create_or_update_enforcement_point_link(
    netbox_obj,
    rulebook_slug: str,
    *,
    policy_object=None,
    comment: str = "",
) -> tuple[EnforcementPointLinkRecord, bool]:
    schema = _require_object_link_schema()
    model = get_object_link_model()
    if model is None:
        raise RuntimeError("link-table COT is not deployed")
    slug = (rulebook_slug or "").strip()
    if not slug:
        raise ValueError("rulebook_slug is required")

    if policy_object is None:
        existing = find_enforcement_point_host_link(netbox_obj, slug)
    else:
        existing = find_enforcement_point_iface_link(netbox_obj, policy_object, slug)

    if existing is not None and existing.instance is not None:
        inst = existing.instance
        changed = False
        new_comment = comment or ""
        if (getattr(inst, "comment", None) or "") != new_comment:
            inst.comment = new_comment
            changed = True
        if changed:
            inst.save()
        return EnforcementPointLinkRecord.from_instance(inst, schema), False

    create_kwargs = {
        "name": link_name_for_enforcement_point(
            netbox_obj,
            slug,
            policy_obj=policy_object,
        ),
        "link_type": LINK_TYPE_ENFORCEMENT_POINT,
        schema.host_field: netbox_obj,
        "rulebook_slug": slug,
        "comment": comment or "",
    }
    if policy_object is not None:
        create_kwargs[schema.policy_field] = policy_object
        create_kwargs["propagation"] = CotObjectLinkPropagationChoices.DIRECT

    inst = model.objects.create(**create_kwargs)
    return EnforcementPointLinkRecord.from_instance(inst, schema), True


def delete_enforcement_point_link(link: EnforcementPointLinkRecord) -> None:
    if link.instance is None:
        raise ValueError("Cannot delete pseudo link record without instance")
    link.instance.delete()


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
        linked = link.policy_object if direction == "fwd" else link.netbox_object
        if linked is None:
            continue
        lct = ContentType.objects.get_for_model(linked)
        covered.add(f"{lct.app_label}__{lct.model}")
    return covered


def create_or_update_links(
    netbox_obj,
    policy_obj,
    *,
    cot_propagation: str,
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
        if getattr(inst, "propagation", None) != cot_propagation:
            inst.propagation = cot_propagation
            changed = True
        new_comment = comment or ""
        if (getattr(inst, "comment", None) or "") != new_comment:
            inst.comment = new_comment
            changed = True
        if changed:
            inst.save()
        return ObjectLinkRecord.from_instance(inst, schema), False

    inst = model.objects.create(
        name=link_name_for_endpoints(netbox_obj, policy_obj),
        link_type=LINK_TYPE_POLICY,
        **{
            schema.host_field: netbox_obj,
            schema.policy_field: policy_obj,
            "propagation": cot_propagation,
            "comment": comment or "",
        },
    )
    return ObjectLinkRecord.from_instance(inst, schema), True


def update_link(
    link: ObjectLinkRecord,
    *,
    cot_propagation: str,
    comment: str = "",
) -> ObjectLinkRecord:
    if link.instance is None:
        raise ValueError("Cannot update pseudo link record without instance")
    inst = link.instance
    inst.propagation = cot_propagation
    inst.comment = comment or ""
    inst.save()
    return ObjectLinkRecord.from_instance(inst)


def delete_link(link: ObjectLinkRecord) -> None:
    if link.instance is None:
        raise ValueError("Cannot delete pseudo link record without instance")
    link.instance.delete()
