"""Apply and diff NSM bundle sections outside COT ``apply_document`` (types only).

COT v1 ``apply_document`` / ``diff_document`` handle ``types`` only. Choice sets
must exist before types are applied; seed objects require types to exist first.
This module uses NetBox / COT REST serializers for those steps instead of raw ORM.
"""

from __future__ import annotations

from typing import Any

__all__ = (
    "apply_choice_sets",
    "apply_seed_objects",
    "diff_choice_sets",
    "diff_seed_objects",
    "serialize_cot_diffs",
)


def _choice_set_extra_choices(spec: dict) -> list[list[str]]:
    return [[str(c), str(c)] for c in spec.get("choices") or []]


def _current_choice_values(choice_set) -> list[str]:
    return [str(value) for value, _label in choice_set.extra_choices or []]


def _iter_choice_set_specs(specs: list | None):
    for spec in specs or []:
        if not isinstance(spec, dict):
            continue
        name = str(spec.get("name", "")).strip()
        if not name:
            continue
        yield spec


_REF_FIELD_TYPES: frozenset[str] | None = None


def _ref_field_types() -> frozenset[str]:
    global _REF_FIELD_TYPES
    if _REF_FIELD_TYPES is None:
        from extras.choices import CustomFieldTypeChoices

        _REF_FIELD_TYPES = frozenset(
            {
                CustomFieldTypeChoices.TYPE_OBJECT,
                CustomFieldTypeChoices.TYPE_MULTIOBJECT,
            }
        )
    return _REF_FIELD_TYPES


def _cot_ref_field_map(cot) -> dict[str, Any]:
    from netbox_custom_objects.models import CustomObjectTypeField

    ref_types = _ref_field_types()
    return {
        field.name: field
        for field in CustomObjectTypeField.objects.filter(custom_object_type=cot)
        if field.type in ref_types
    }


def _resolve_portable_ref(ref: str) -> tuple[Any, Any]:
    """Resolve ``cot_slug/object_name`` to ``(instance, ContentType)``."""
    from django.contrib.contenttypes.models import ContentType
    from netbox_custom_objects.models import CustomObjectType

    if "/" not in ref:
        raise ValueError(
            f"Invalid portable reference (expected 'type/name'): {ref!r}"
        )
    slug, obj_name = ref.split("/", 1)
    slug = slug.strip()
    obj_name = obj_name.strip()
    if not slug or not obj_name:
        raise ValueError(f"Invalid portable reference: {ref!r}")

    cot = CustomObjectType.objects.filter(slug=slug).first()
    if cot is None:
        raise ValueError(
            f"Custom object type not found for portable reference: {slug!r}"
        )
    model = cot.get_model()
    instance = model.objects.filter(name=obj_name).first()
    if instance is None:
        raise ValueError(f"Object not found for portable reference: {ref!r}")
    content_type = ContentType.objects.get_for_model(model)
    return instance, content_type


def _resolve_reference_value(field, value: Any) -> Any:
    if isinstance(value, int) or isinstance(value, dict):
        return value
    if not isinstance(value, str) or "/" not in value:
        return value

    instance, content_type = _resolve_portable_ref(value)
    if field.is_polymorphic:
        return {
            "content_type_id": content_type.pk,
            "object_id": instance.pk,
        }
    return instance.pk


def _resolve_payload_references(cot, payload: dict[str, Any]) -> dict[str, Any]:
    from extras.choices import CustomFieldTypeChoices

    ref_fields = _cot_ref_field_map(cot)
    if not ref_fields:
        return payload

    resolved = dict(payload)
    for key, value in payload.items():
        if key == "name" or key not in ref_fields:
            continue
        field = ref_fields[key]
        if field.type == CustomFieldTypeChoices.TYPE_MULTIOBJECT:
            if isinstance(value, list):
                resolved[key] = [
                    _resolve_reference_value(field, item) for item in value
                ]
            else:
                resolved[key] = _resolve_reference_value(field, value)
        else:
            resolved[key] = _resolve_reference_value(field, value)
    return resolved


def _current_ref_field_value(instance, field) -> Any:
    from django.apps import apps as django_apps
    from extras.choices import CustomFieldTypeChoices

    from netbox_custom_objects.constants import APP_LABEL

    if field.type == CustomFieldTypeChoices.TYPE_MULTIOBJECT:
        if field.is_polymorphic:
            through = django_apps.get_model(APP_LABEL, field.through_model_name)
            return sorted(
                through.objects.filter(source_id=instance.pk).values_list(
                    "content_type_id", "object_id"
                )
            )
        related = getattr(instance, field.name, None)
        if related is not None and hasattr(related, "values_list"):
            return sorted(related.values_list("pk", flat=True))
        return []
    if field.type == CustomFieldTypeChoices.TYPE_OBJECT:
        if field.is_polymorphic:
            ct_value = getattr(instance, f"{field.name}_content_type", None)
            obj_value = getattr(instance, f"{field.name}_object_id", None)
            if ct_value and obj_value:
                return (ct_value.pk, obj_value)
            return None
        related = getattr(instance, field.name, None)
        return getattr(related, "pk", None)
    return getattr(instance, field.name, None)


def _desired_ref_field_value(value: Any, field) -> Any:
    from extras.choices import CustomFieldTypeChoices

    if field.type == CustomFieldTypeChoices.TYPE_MULTIOBJECT:
        if field.is_polymorphic:
            items = value if isinstance(value, list) else [value]
            normalized = []
            for item in items:
                if isinstance(item, dict):
                    normalized.append(
                        (item["content_type_id"], item["object_id"])
                    )
                else:
                    normalized.append(item)
            return sorted(normalized)
        if isinstance(value, list):
            return sorted(value)
        return [value]
    if field.type == CustomFieldTypeChoices.TYPE_OBJECT and field.is_polymorphic:
        if isinstance(value, dict):
            return (value["content_type_id"], value["object_id"])
        return value
    return value


def _record_payload(record: dict) -> dict[str, Any] | None:
    from netbox_nsm.bundles.schema_builder import slugify_identifier

    obj_name = str(record.get("name", "")).strip()
    if not obj_name:
        return None
    payload: dict[str, Any] = {"name": obj_name}
    for key, value in record.items():
        if key == "name":
            continue
        payload[slugify_identifier(key)] = value
    return payload


def serialize_cot_diffs(diffs) -> list[dict[str, Any]]:
    """JSON-serialisable COT diffs (same shape as SchemaPreviewView)."""
    return [_serialize_cot_diff(diff) for diff in diffs]


def _serialize_field_change(fc) -> dict[str, Any]:
    result = {
        "op": fc.op.value,
        "schema_id": fc.schema_id,
        "db_name": fc.db_name,
        "schema_def": fc.schema_def,
    }
    if fc.changed_attrs:
        result["changed_attrs"] = {k: list(v) for k, v in fc.changed_attrs.items()}
    return result


def _serialize_cot_diff(diff) -> dict[str, Any]:
    return {
        "slug": diff.slug,
        "name": diff.name,
        "is_new": diff.is_new,
        "has_changes": diff.has_changes,
        "has_destructive_changes": diff.has_destructive_changes,
        "cot_changes": {k: list(v) for k, v in diff.cot_changes.items()},
        "field_changes": [_serialize_field_change(fc) for fc in diff.field_changes],
        "warnings": diff.warnings,
    }


def diff_choice_sets(specs: list | None) -> list[dict[str, Any]]:
    """Compare bundle ``choice_sets`` against ``CustomFieldChoiceSet`` rows."""
    from extras.models import CustomFieldChoiceSet

    diffs: list[dict[str, Any]] = []
    for spec in _iter_choice_set_specs(specs):
        name = str(spec["name"])
        desired = [str(c) for c in spec.get("choices") or []]
        choice_set = CustomFieldChoiceSet.objects.filter(name=name).first()
        if choice_set is None:
            diffs.append({"name": name, "op": "add", "desired_choices": desired})
            continue
        current = _current_choice_values(choice_set)
        if current != desired:
            diffs.append(
                {
                    "name": name,
                    "op": "alter",
                    "current_choices": current,
                    "desired_choices": desired,
                }
            )
    return diffs


def apply_choice_sets(specs: list | None) -> int:
    """Create or update choice sets via ``CustomFieldChoiceSetSerializer``."""
    from extras.api.serializers_.customfields import CustomFieldChoiceSetSerializer
    from extras.models import CustomFieldChoiceSet

    count = 0
    for spec in _iter_choice_set_specs(specs):
        name = str(spec["name"])
        data = {
            "name": name,
            "extra_choices": _choice_set_extra_choices(spec),
        }
        instance = CustomFieldChoiceSet.objects.filter(name=name).first()
        serializer = CustomFieldChoiceSetSerializer(
            instance,
            data=data,
            partial=bool(instance),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        count += 1
    return count


def diff_seed_objects(objects: list | None) -> list[dict[str, Any]]:
    """Compare bundle ``objects`` seed records against live custom object rows."""
    from netbox_custom_objects.models import CustomObjectType

    diffs: list[dict[str, Any]] = []
    for entry in objects or []:
        if not isinstance(entry, dict):
            continue
        slug = str(entry.get("type", "")).strip()
        if not slug:
            continue
        cot = CustomObjectType.objects.filter(slug=slug).first()
        if cot is None:
            pending = [
                str(record.get("name", "")).strip()
                for record in entry.get("records") or []
                if isinstance(record, dict) and str(record.get("name", "")).strip()
            ]
            if pending:
                diffs.append(
                    {
                        "type": slug,
                        "op": "pending",
                        "reason": "type_not_in_db",
                        "names": pending,
                    }
                )
            continue
        model = cot.get_model()
        ref_fields = _cot_ref_field_map(cot)
        for record in entry.get("records") or []:
            if not isinstance(record, dict):
                continue
            payload = _record_payload(record)
            if payload is None:
                continue
            payload = _resolve_payload_references(cot, payload)
            obj_name = payload["name"]
            instance = model.objects.filter(name=obj_name).first()
            if instance is None:
                diffs.append(
                    {
                        "type": slug,
                        "name": obj_name,
                        "op": "add",
                        "fields": {
                            key: value
                            for key, value in payload.items()
                            if key != "name"
                        },
                    }
                )
                continue
            changed = {}
            for key, value in payload.items():
                if key == "name":
                    continue
                field = ref_fields.get(key)
                if field is not None:
                    current = _current_ref_field_value(instance, field)
                    desired = _desired_ref_field_value(value, field)
                    if current != desired:
                        changed[key] = {"current": current, "desired": desired}
                elif getattr(instance, key, None) != value:
                    changed[key] = {
                        "current": getattr(instance, key),
                        "desired": value,
                    }
            if changed:
                diffs.append(
                    {
                        "type": slug,
                        "name": obj_name,
                        "op": "alter",
                        "changes": changed,
                    }
                )
    return diffs


def apply_seed_objects(objects: list | None) -> int:
    """Upsert seed records via COT ``get_serializer_class`` dynamic serializers."""
    from netbox_custom_objects.api.serializers import get_serializer_class
    from netbox_custom_objects.models import CustomObjectType

    seeded = 0
    for entry in objects or []:
        if not isinstance(entry, dict):
            continue
        slug = str(entry.get("type", "")).strip()
        if not slug:
            continue
        cot = CustomObjectType.objects.filter(slug=slug).first()
        if cot is None:
            continue
        model = cot.get_model()
        serializer_class = get_serializer_class(model)
        for record in entry.get("records") or []:
            if not isinstance(record, dict):
                continue
            payload = _record_payload(record)
            if payload is None:
                continue
            payload = _resolve_payload_references(cot, payload)
            instance = model.objects.filter(name=payload["name"]).first()
            serializer = serializer_class(
                instance,
                data=payload,
                partial=bool(instance),
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            seeded += 1
    return seeded
