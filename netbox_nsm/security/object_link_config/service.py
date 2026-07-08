"""Read/write ``nsm_object_link`` polymorphic Object A/B type lists."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from django.contrib.contenttypes.models import ContentType

from netbox_nsm.core.display_utils import ct_display_label

__all__ = (
    "apply_object_link_schema_changes",
    "attach_link_usage_counts",
    "build_object_link_portable_document",
    "clear_object_link_config_caches",
    "content_type_to_portable_ref",
    "get_object_link_config_state",
    "link_usage_counts_for_side",
    "portable_ref_to_content_type",
    "preview_object_link_schema_changes",
    "split_object_link_types",
)

# Policy-side link targets (Security object); not rulebook field types like Action.
OBJECT_LINK_SECURITY_EXCLUDED_SLUGS: frozenset[str] = frozenset(
    {
        "nsm_action",
        "nsm_object_link",
    }
)


def content_type_to_portable_ref(ct) -> str:
    """Map a Django ContentType to portable-schema ``related_object_types`` ref."""
    if ct.app_label == "netbox_custom_objects":
        try:
            from netbox_custom_objects import constants
            from netbox_custom_objects.models import CustomObjectType

            match = constants.TABLE_MODEL_RE.match(ct.model)
            if match:
                slug = (
                    CustomObjectType.objects.filter(pk=int(match.group(1)))
                    .values_list("slug", flat=True)
                    .first()
                )
                if slug:
                    return f"custom-objects/{slug}"
        except Exception:
            pass
    return f"{ct.app_label}/{ct.model}"


def portable_ref_to_content_type(ref: str):
    """Resolve a portable-schema ref to a ContentType (or ``None``)."""
    ref = (ref or "").strip()
    if not ref:
        return None
    if ref.startswith("custom-objects/"):
        slug = ref.split("/", 1)[1]
        try:
            from netbox_custom_objects.models import CustomObjectType

            cot = CustomObjectType.objects.filter(slug=slug).first()
            if cot is None:
                return None
            return ContentType.objects.get_for_model(cot.get_model())
        except Exception:
            return None
    if "/" not in ref:
        return None
    app_label, model = ref.split("/", 1)
    try:
        return ContentType.objects.get(app_label=app_label, model=model)
    except ContentType.DoesNotExist:
        return None


def _field_related_refs(field) -> list[str]:
    refs: list[str] = []
    related = getattr(field, "related_object_type", None)
    if related is not None and getattr(related, "pk", None):
        refs.append(content_type_to_portable_ref(related))
    try:
        for ct in field.related_object_types.all():
            refs.append(content_type_to_portable_ref(ct))
    except Exception:
        pass
    return sorted(set(refs))


def _ref_label(ref: str) -> str:
    ct = portable_ref_to_content_type(ref)
    if ct is None:
        return ref
    try:
        from netbox_nsm.type_metadata.config import resolve_nsm_config_for_content_type

        cfg = resolve_nsm_config_for_content_type(ct.pk)
        if cfg is not None:
            return cfg.name
    except Exception:
        pass
    return ct.model_class()._meta.verbose_name.title() if ct.model_class() else ref


def _security_candidate_refs(current_security_refs: list[str] | None = None) -> list[str]:
    """Return picker refs for the Security-object side.

    All deployed Custom Object types are eligible except the link-table COT and
    other explicitly excluded slugs. The active subset is persisted only on the
    link-table COT field ``related_object_types``.
    """
    refs = set(current_security_refs or [])
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return sorted(refs)

    for cot in CustomObjectType.objects.all():
        if cot.slug in OBJECT_LINK_SECURITY_EXCLUDED_SLUGS:
            continue
        ct = ContentType.objects.get_for_model(cot.get_model())
        refs.add(content_type_to_portable_ref(ct))
    return sorted(refs)


def _host_candidate_refs(current_host_refs: list[str]) -> list[str]:
    """Return picker refs for the Netbox-object side.

    Eligible types come from NetBox ``ObjectType.public()`` (same universe as the
    Security tab on built-in models). The active subset is persisted only on the
    link-table COT field ``related_object_types`` — never from a Python whitelist.
    """
    from netbox_nsm.security.tab.registry import _public_host_model_classes

    refs = set(current_host_refs)
    for model in _public_host_model_classes():
        refs.add(content_type_to_portable_ref(ContentType.objects.get_for_model(model)))
    return sorted(refs)


def _type_entry(ref: str, *, selected: bool) -> dict[str, Any]:
    ct = portable_ref_to_content_type(ref)
    display_label = ct_display_label(ct) if ct is not None else ref
    return {
        "ref": ref,
        "label": _ref_label(ref),
        "display_label": display_label,
        "content_type_id": ct.pk if ct is not None else None,
        "selected": selected,
    }


def split_object_link_types(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Split type entries into selected and still-available candidates."""
    selected = sorted(
        (entry for entry in entries if entry.get("selected")),
        key=lambda entry: (entry.get("display_label") or entry.get("ref") or "").lower(),
    )
    available = sorted(
        (entry for entry in entries if not entry.get("selected")),
        key=lambda entry: (entry.get("display_label") or entry.get("ref") or "").lower(),
    )
    return {"selected": selected, "available": available}


def link_usage_counts_for_side(side: str) -> dict[int, int]:
    """Return link-table row counts keyed by content type ID for one Object Link side."""
    from django.db.models import Count

    from netbox_nsm.security.links.cot_link_schema import get_object_link_schema
    from netbox_nsm.security.links.object_link_service import get_object_link_model

    schema = get_object_link_schema()
    model = get_object_link_model()
    if schema is None or model is None:
        return {}

    if side == "host":
        ct_field = f"{schema.host_field}_content_type_id"
    elif side == "security":
        ct_field = f"{schema.security_field}_content_type_id"
    else:
        raise ValueError(f"unknown side: {side}")

    return {
        row[ct_field]: row["count"]
        for row in model.objects.values(ct_field)
        .annotate(count=Count("pk"))
        .filter(**{f"{ct_field}__isnull": False})
    }


def attach_link_usage_counts(entries: list[dict[str, Any]], *, side: str) -> None:
    """Annotate selected type rows with link usage counts for the UI."""
    counts = link_usage_counts_for_side(side)
    for entry in entries:
        ct_id = entry.get("content_type_id")
        usage = counts.get(ct_id, 0) if ct_id is not None else 0
        entry["usage_count"] = usage
        entry["can_remove"] = usage == 0


def prepare_object_link_type_panels(
    state: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """Split host/security types and attach link usage counts for selected rows."""
    host_types = split_object_link_types(state["host_types"])
    security_types = split_object_link_types(state["security_types"])
    attach_link_usage_counts(host_types["selected"], side="host")
    attach_link_usage_counts(security_types["selected"], side="security")
    return host_types, security_types


def get_object_link_config_state() -> dict[str, Any] | None:
    """Return overview state for the link-table COT, or ``None`` if not deployed."""
    from netbox_nsm.security.links.cot_link_schema import (
        get_object_link_schema,
        object_fields_for_cot,
    )

    schema = get_object_link_schema()
    if schema is None:
        return None

    host_field = security_field = None
    for field in object_fields_for_cot(schema.cot):
        if field.name == schema.host_field:
            host_field = field
        elif field.name == schema.security_field:
            security_field = field
    if host_field is None or security_field is None:
        return None

    host_refs = _field_related_refs(host_field)
    security_refs = _field_related_refs(security_field)
    host_candidates = _host_candidate_refs(host_refs)
    security_candidates = _security_candidate_refs(security_refs)

    return {
        "cot_slug": schema.cot.slug,
        "host_field": schema.host_field,
        "security_field": schema.security_field,
        "host_types": [
            _type_entry(ref, selected=ref in host_refs) for ref in host_candidates
        ],
        "security_types": [
            _type_entry(ref, selected=ref in security_refs) for ref in security_candidates
        ],
        "host_refs": host_refs,
        "security_refs": security_refs,
    }


def _load_bundle_type_def() -> dict:
    from netbox_nsm.bundles.dispatch import load_bundle
    from netbox_nsm.bundles.paths import bundle_json_path

    bundle = load_bundle(bundle_json_path("nsm_schema"))
    for type_def in bundle.get("types") or []:
        if isinstance(type_def, dict) and type_def.get("slug") == "nsm_object_link":
            return deepcopy(type_def)
    raise ValueError("nsm_object_link type definition not found in nsm_schema bundle")


def build_object_link_portable_document(
    host_refs: list[str],
    security_refs: list[str],
) -> dict:
    """Build a portable-schema document updating only Object A/B ``related_object_types``."""
    type_def = _load_bundle_type_def()
    host_set = set(host_refs)
    security_set = set(security_refs)
    for field_def in type_def.get("fields") or []:
        if not isinstance(field_def, dict):
            continue
        name = field_def.get("name")
        if name == "netbox_object":
            field_def["related_object_types"] = sorted(host_set)
        elif name == "security_object":
            field_def["related_object_types"] = sorted(security_set)
    return {
        "schema_version": "1",
        "types": [type_def],
    }


def _count_links_with_removed_endpoints(
    *,
    removed_host_ct_ids: set[int],
    removed_security_ct_ids: set[int],
) -> int:
    from netbox_nsm.security.links.cot_link_schema import get_object_link_schema
    from netbox_nsm.security.links.object_link_service import get_object_link_model

    schema = get_object_link_schema()
    model = get_object_link_model()
    if schema is None or model is None:
        return 0
    if not removed_host_ct_ids and not removed_security_ct_ids:
        return 0

    count = 0
    host_ct_field = f"{schema.host_field}_content_type_id"
    security_ct_field = f"{schema.security_field}_content_type_id"
    for row in model.objects.all().only(
        host_ct_field,
        f"{schema.host_field}_object_id",
        security_ct_field,
        f"{schema.security_field}_object_id",
    ):
        host_ct_id = getattr(row, host_ct_field, None)
        security_ct_id = getattr(row, security_ct_field, None)
        if host_ct_id in removed_host_ct_ids or security_ct_id in removed_security_ct_ids:
            count += 1
    return count


def preview_object_link_schema_changes(
    host_refs: list[str],
    security_refs: list[str],
) -> dict[str, Any]:
    """Return diff + impact for proposed Object A/B type lists."""
    from netbox_custom_objects.schema.executor import diff_document

    from netbox_nsm.bundles.bundle_extensions import serialize_cot_diffs

    state = get_object_link_config_state()
    if state is None:
        raise ValueError("link-table COT is not deployed")

    current_host = set(state["host_refs"])
    current_security = set(state["security_refs"])
    new_host = set(host_refs)
    new_security = set(security_refs)

    removed_host = current_host - new_host
    removed_security = current_security - new_security
    removed_host_ct_ids = {
        ct.pk
        for ref in removed_host
        if (ct := portable_ref_to_content_type(ref)) is not None
    }
    removed_security_ct_ids = {
        ct.pk
        for ref in removed_security
        if (ct := portable_ref_to_content_type(ref)) is not None
    }

    document = build_object_link_portable_document(host_refs, security_refs)
    cot_diffs = diff_document(document)
    impact_count = _count_links_with_removed_endpoints(
        removed_host_ct_ids=removed_host_ct_ids,
        removed_security_ct_ids=removed_security_ct_ids,
    )

    return {
        "host_added": sorted(new_host - current_host),
        "host_removed": sorted(removed_host),
        "security_added": sorted(new_security - current_security),
        "security_removed": sorted(removed_security),
        "impact_count": impact_count,
        "destructive": impact_count > 0,
        "cot_diff": serialize_cot_diffs(cot_diffs),
        "destructive_blocked": any(d.has_destructive_changes for d in cot_diffs),
    }


def clear_object_link_config_caches() -> None:
    from netbox_nsm.security.tab.eligibility import clear_object_link_eligibility_cache

    clear_object_link_eligibility_cache()
    try:
        from netbox_nsm.core.cot_m2m_through import through_table_column_names

        through_table_column_names.cache_clear()
    except Exception:
        pass


def _resolve_refs_to_object_types(refs: list[str]):
    """Resolve portable refs to ``core.ObjectType`` rows for M2M assignment."""
    from core.models import ObjectType

    resolved = []
    seen: set[int] = set()
    for ref in refs:
        ct = portable_ref_to_content_type(ref)
        if ct is None:
            continue
        try:
            object_type = ObjectType.objects.get(app_label=ct.app_label, model=ct.model)
        except ObjectType.DoesNotExist:
            continue
        if object_type.pk not in seen:
            resolved.append(object_type)
            seen.add(object_type.pk)
    return resolved


def _get_object_link_endpoint_fields():
    from netbox_nsm.security.links.cot_link_schema import (
        get_object_link_schema,
        object_fields_for_cot,
    )

    schema = get_object_link_schema()
    if schema is None:
        return None, None, None

    host_field = security_field = None
    for field in object_fields_for_cot(schema.cot):
        if field.name == schema.host_field:
            host_field = field
        elif field.name == schema.security_field:
            security_field = field
    return schema, host_field, security_field


def _apply_object_link_related_types(host_refs: list[str], security_refs: list[str]) -> None:
    """Update Object Link endpoint ``related_object_types`` on live COT fields.

    Object Link config only changes the polymorphic allow-lists. Using the full
    portable-schema apply path would attempt to ADD fields whose DB columns
    already exist when ``schema_id`` was never backfilled (e.g. ``security_object``).
    """
    _schema, host_field, security_field = _get_object_link_endpoint_fields()
    if host_field is None or security_field is None:
        raise ValueError("link-table COT is not deployed")

    host_field.related_object_types.set(_resolve_refs_to_object_types(host_refs))
    security_field.related_object_types.set(_resolve_refs_to_object_types(security_refs))


def apply_object_link_schema_changes(
    host_refs: list[str],
    security_refs: list[str],
    *,
    allow_destructive: bool = False,
) -> dict[str, Any]:
    """Apply Object A/B type list changes in-place."""
    preview = preview_object_link_schema_changes(host_refs, security_refs)
    if preview["destructive"] and not allow_destructive:
        raise ValueError(
            f"Removing types would affect {preview['impact_count']} link row(s). "
            "Enable destructive changes to proceed."
        )

    _apply_object_link_related_types(host_refs, security_refs)
    clear_object_link_config_caches()
    return preview
