"""Security Panel assignments via ``nsm_object_link`` COT (source of truth)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from django.contrib.contenttypes.models import ContentType

from netbox_nsm.models import TypeConfig
from netbox_nsm.models.object_link import LinkPropagationChoices
from netbox_nsm.objects.link_propagation import (
    CotObjectLinkPropagationChoices,
    cot_propagation_to_native,
)

__all__ = (
    "NSM_OBJECT_LINK_SLUG",
    "ObjectLinkRecord",
    "build_panel_link_groups",
    "classify_link_endpoints",
    "create_or_update_links",
    "delete_link",
    "direct_nsm_type_keys_for_object",
    "find_link_between",
    "get_link_by_pk",
    "get_object_link_model",
    "iter_links_for_object",
    "iter_links_on_container",
    "iter_links_stored_on_netbox_object",
    "link_name_for_endpoints",
    "update_link",
)

NSM_OBJECT_LINK_SLUG = "nsm_object_link"

_INHERIT_IPAM_COT = (
    CotObjectLinkPropagationChoices.INHERIT_IPAM,
    CotObjectLinkPropagationChoices.INHERIT_IPAM_STOP,
)
_INHERIT_GROUP_COT = (
    CotObjectLinkPropagationChoices.INHERIT_GROUP,
    CotObjectLinkPropagationChoices.INHERIT_GROUP_STOP,
)


def get_object_link_model():
    """Return the dynamic model for ``nsm_object_link``, or ``None``."""
    try:
        from netbox_custom_objects.models import CustomObjectType

        cot = CustomObjectType.objects.filter(slug=NSM_OBJECT_LINK_SLUG).first()
        if cot is None:
            return None
        return cot.get_model()
    except Exception:
        return None


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

    Policy side is identified via TypeConfig panel-linkable types; if both or
    neither match, *object_a* is treated as netbox host (legacy ObjectLink A).
    """
    ct_a = ContentType.objects.get_for_model(object_a)
    ct_b = ContentType.objects.get_for_model(object_b)
    a_policy = TypeConfig.queryset_panel_linkable().filter(content_type=ct_a).exists()
    b_policy = TypeConfig.queryset_panel_linkable().filter(content_type=ct_b).exists()
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
    policy_object: object | None = None

    @classmethod
    def from_instance(cls, instance) -> ObjectLinkRecord:
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
            netbox_object=getattr(instance, "netbox_object", None),
            policy_object=getattr(instance, "policy_object", None),
        )

    @property
    def cot_propagation(self) -> str:
        if self.instance is not None:
            return getattr(
                self.instance,
                "propagation",
                CotObjectLinkPropagationChoices.DIRECT,
            )
        from netbox_nsm.objects.link_propagation import native_propagation_to_cot

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

    def get_propagation_display(self) -> str:
        from netbox_nsm.objects.link_propagation import cot_propagation_display

        return cot_propagation_display(self.cot_propagation)

    def __str__(self) -> str:
        return f"{self.netbox_object} ↔ {self.policy_object}"


def get_link_by_pk(pk: int) -> ObjectLinkRecord | None:
    model = get_object_link_model()
    if model is None:
        return None
    try:
        return ObjectLinkRecord.from_instance(model.objects.get(pk=pk))
    except model.DoesNotExist:
        return None


def find_link_between(object_a, object_b) -> ObjectLinkRecord | None:
    """Find assignment between page object *object_a* and linked row *object_b*."""
    if object_a is None or object_b is None:
        return None
    model = get_object_link_model()
    if model is None:
        return None

    netbox, policy = classify_link_endpoints(object_a, object_b)
    for row in _filter_instances_by_object_ref(model, "netbox_object", netbox):
        row_policy = getattr(row, "policy_object", None)
        if row_policy is None:
            continue
        if row_policy.pk == policy.pk and ContentType.objects.get_for_model(
            row_policy
        ) == ContentType.objects.get_for_model(policy):
            return ObjectLinkRecord.from_instance(row)
    return None


def iter_links_stored_on_netbox_object(netbox_obj) -> Iterator[ObjectLinkRecord]:
    """Yield links where ``netbox_object`` equals *netbox_obj* (assign host)."""
    for link, direction in iter_links_for_object(netbox_obj):
        if direction == "fwd":
            yield link


def iter_links_for_object(obj) -> Iterator[tuple[ObjectLinkRecord, str]]:
    """
    Yield ``(link, direction)`` for Security Panel display.

    ``direction`` is ``fwd`` when *obj* is ``netbox_object`` (shows policy_object),
    ``rev`` when *obj* is ``policy_object`` (shows netbox_object).
    """
    model = get_object_link_model()
    if model is None or obj is None:
        return

    seen: set[int] = set()
    for row in _filter_instances_by_object_ref(model, "netbox_object", obj):
        if row.pk in seen:
            continue
        seen.add(row.pk)
        yield ObjectLinkRecord.from_instance(row), "fwd"

    for row in _filter_instances_by_object_ref(model, "policy_object", obj):
        if row.pk in seen:
            continue
        seen.add(row.pk)
        yield ObjectLinkRecord.from_instance(row), "rev"


def iter_links_on_container(
    container_obj,
    *,
    inherit_mode: str,
) -> Iterator[ObjectLinkRecord]:
    """Yield inheriting links stored on *container_obj* (prefix, group, …)."""
    model = get_object_link_model()
    if model is None:
        return

    if inherit_mode == LinkPropagationChoices.INHERIT_IPAM:
        allowed_cot = _INHERIT_IPAM_COT
    elif inherit_mode == LinkPropagationChoices.INHERIT_GROUP:
        allowed_cot = _INHERIT_GROUP_COT
    else:
        return

    for row in _filter_instances_by_object_ref(model, "netbox_object", container_obj):
        prop = getattr(row, "propagation", "")
        if prop not in allowed_cot:
            continue
        yield ObjectLinkRecord.from_instance(row)


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


def build_panel_link_groups(
    obj,
    *,
    return_url: str | None,
    panel_link_payload,
    object_link_action_urls,
    type_label_fn,
) -> tuple[list[dict], int]:
    """Build link-type groups for ``NsmSecurityLinksExtension``."""
    from django.db.models import prefetch_related_objects

    from netbox_nsm.core.display_utils import get_display_template_map
    from netbox_nsm.objects.link_propagation import object_link_panel_user_comment
    from netbox_nsm.template_content import _finalize_link_type_groups

    if obj is None or not getattr(obj, "pk", None):
        return [], 0

    tmpl_map = get_display_template_map()
    links_by_type: dict = {}
    seen_keys: set[tuple] = set()

    link_pairs = list(iter_links_for_object(obj))
    instances = [link.instance for link, _ in link_pairs if link.instance is not None]
    prefetch_related_objects(instances, "netbox_object", "policy_object")

    for link, direction in link_pairs:
        linked = link.policy_object if direction == "fwd" else link.netbox_object
        if linked is None:
            continue
        lct = ContentType.objects.get_for_model(linked)
        type_key = f"{lct.app_label}__{lct.model}"
        dedupe = (type_key, linked.pk)
        if dedupe in seen_keys:
            continue
        seen_keys.add(dedupe)
        if type_key not in links_by_type:
            links_by_type[type_key] = {
                "label": type_label_fn(lct),
                "objects": [],
            }
        links_by_type[type_key]["objects"].append(
            panel_link_payload(
                linked,
                lct,
                tmpl_map,
                comment=object_link_panel_user_comment(link),
                **object_link_action_urls(link, return_url),
            )
        )

    link_type_groups = _finalize_link_type_groups(
        [
            {
                "type_key": k,
                "type_label": v["label"],
                "count": len(v["objects"]),
                "objects": v["objects"],
            }
            for k, v in sorted(links_by_type.items(), key=lambda x: x[1]["label"])
        ]
    )
    total_links = sum(g["count"] for g in link_type_groups)
    return link_type_groups, total_links


def create_or_update_links(
    netbox_obj,
    policy_obj,
    *,
    cot_propagation: str,
    comment: str = "",
) -> tuple[ObjectLinkRecord, bool]:
    """Create or update one ``nsm_object_link`` row. Returns ``(link, created)``."""
    model = get_object_link_model()
    if model is None:
        raise RuntimeError("nsm_object_link COT is not deployed")

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
        return ObjectLinkRecord.from_instance(inst), False

    inst = model.objects.create(
        name=link_name_for_endpoints(netbox_obj, policy_obj),
        netbox_object=netbox_obj,
        policy_object=policy_obj,
        propagation=cot_propagation,
        comment=comment or "",
    )
    return ObjectLinkRecord.from_instance(inst), True


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
