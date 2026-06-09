"""Rulebook template definitions for NSM Custom-Object rulebooks.

Templates are deployed as ``CustomObjectType`` rows in group **NSM Rulebook
Templates** (slugs ``nsm_rb_0001_template``, …). They are blueprints only.

Concrete rulebooks use slugs ``nsm_rb_<name>`` in group **NSM Rulebooks** and
are created by cloning a template schema via ``build_rulebook_document``.
"""

from __future__ import annotations

from copy import deepcopy

from netbox_nsm.rulebooks.rulebook_groups import (
    GROUP_ACTIONS,
    GROUP_COMMON,
    GROUP_DESTINATION,
    GROUP_INFOS,
    GROUP_NOTES,
    GROUP_SERVICES,
    GROUP_SOURCE,
    resolve_group_name_for_display,
    rulebook_field_group_name,
)

__all__ = (
    "BUNDLED_RULEBOOK_TEMPLATE_SLUGS",
    "DEMO_RULEBOOK_SLUG",
    "DEMO_RULEBOOK_TEMPLATE_SLUG",
    "RULEBOOK_GROUP",
    "RULEBOOK_TEMPLATE_GROUP",
    "RULEBOOK_TEMPLATE_SLUGS",
    "RULEBOOK_TEMPLATE_BY_SLUG",
    "build_rulebook_document",
    "build_rulebook_template_type_defs",
    "format_rulebook_display_name",
    "get_rulebook_template_slugs",
    "iter_rulebook_template_choices",
    "normalize_rulebook_display_name",
    "get_template",
    "is_deployed_rulebook_slug",
    "is_rulebook_template_slug",
    "template_wizard_columns",
)

RULEBOOK_TEMPLATE_GROUP = "NSM Rulebook Templates"
RULEBOOK_GROUP = "NSM Rulebooks"

# Canonical field definitions shared across templates.
_FIELD_CATALOG: dict[str, dict] = {
    "index": {
        "id": 1,
        "name": "index",
        "type": "integer",
        "label": "Index",
        "description": "Rule sequence number (primary key).",
        "required": True,
        "weight": 1,
        "primary": True,
        "group_name": GROUP_COMMON,
    },
    "status": {
        "id": 2,
        "name": "status",
        "type": "boolean",
        "label": "Status",
        "description": "When false, the rule is disabled.",
        "required": False,
        "weight": 2,
        "group_name": GROUP_COMMON,
    },
    "name": {
        "id": 3,
        "name": "name",
        "type": "text",
        "label": "Name",
        "description": "Optional short rule name.",
        "required": False,
        "weight": 3,
        "group_name": GROUP_COMMON,
    },
    "source_zones": {
        "id": 4,
        "name": "source_zones",
        "type": "multiobject",
        "label": "Zones",
        "group_name": GROUP_SOURCE,
        "description": "Source objects: zones",
        "required": True,
        "weight": 11,
        "is_polymorphic": True,
        "related_object_types": ["custom-objects/nsm_zone"],
    },
    "destination_zones": {
        "id": 5,
        "name": "destination_zones",
        "type": "multiobject",
        "label": "Zones",
        "group_name": GROUP_DESTINATION,
        "description": "Destination objects: zones",
        "required": True,
        "weight": 21,
        "is_polymorphic": True,
        "related_object_types": ["custom-objects/nsm_zone"],
    },
    "source_labels": {
        "id": 12,
        "name": "source_labels",
        "type": "multiobject",
        "label": "Labels",
        "group_name": GROUP_SOURCE,
        "description": "Source objects: labels",
        "required": False,
        "weight": 12,
        "is_polymorphic": True,
        "related_object_types": ["custom-objects/nsm_label"],
    },
    "destination_labels": {
        "id": 13,
        "name": "destination_labels",
        "type": "multiobject",
        "label": "Labels",
        "group_name": GROUP_DESTINATION,
        "description": "Destination objects: labels",
        "required": False,
        "weight": 22,
        "is_polymorphic": True,
        "related_object_types": ["custom-objects/nsm_label"],
    },
    "source_addresses": {
        "id": 6,
        "name": "source_addresses",
        "type": "multiobject",
        "label": "Addresses",
        "group_name": GROUP_SOURCE,
        "description": "Source objects: addresses and address groups",
        "required": True,
        "weight": 13,
        "is_polymorphic": True,
        "related_object_types": [
            "custom-objects/nsm_address",
            "custom-objects/nsm_address_group",
        ],
    },
    "destination_addresses": {
        "id": 7,
        "name": "destination_addresses",
        "type": "multiobject",
        "label": "Addresses",
        "group_name": GROUP_DESTINATION,
        "description": "Destination objects: addresses and address groups",
        "required": True,
        "weight": 23,
        "is_polymorphic": True,
        "related_object_types": [
            "custom-objects/nsm_address",
            "custom-objects/nsm_address_group",
        ],
    },
    "services_applications": {
        "id": 8,
        "name": "services_applications",
        "type": "multiobject",
        "label": "Services & Applications",
        "group_name": GROUP_SERVICES,
        "description": "Service objects: service, service group, and network app.",
        "required": True,
        "weight": 40,
        "is_polymorphic": True,
        "related_object_types": [
            "custom-objects/nsm_service",
            "custom-objects/nsm_service_group",
            "custom-objects/nsm_app_network",
        ],
    },
    "actions": {
        "id": 9,
        "name": "actions",
        "type": "multiobject",
        "label": "Actions",
        "group_name": GROUP_ACTIONS,
        "description": "Rule outcome(s), e.g. permit or deny.",
        "required": True,
        "weight": 50,
        "related_object_type": "custom-objects/nsm_action",
    },
    "infos": {
        "id": 10,
        "name": "infos",
        "type": "multiobject",
        "label": "Infos",
        "group_name": GROUP_INFOS,
        "description": "Informational objects, e.g. business app (documentation column).",
        "required": False,
        "weight": 60,
        "related_object_type": "custom-objects/nsm_app_business",
    },
    "description": {
        "id": 11,
        "name": "description",
        "type": "longtext",
        "label": "Description",
        "group_name": GROUP_NOTES,
        "description": "Free-text rule description.",
        "required": False,
        "weight": 100,
    },
}

_OBJECT_TYPE_LABELS: dict[str, str] = {
    "custom-objects/nsm_zone": "Zone",
    "custom-objects/nsm_label": "Label",
    "custom-objects/nsm_address": "Address",
    "custom-objects/nsm_address_group": "Address Group",
    "custom-objects/nsm_service": "Service",
    "custom-objects/nsm_service_group": "Service Group",
    "custom-objects/nsm_app_network": "Network App",
    "custom-objects/nsm_action": "Action",
    "custom-objects/nsm_app_business": "Business App",
}

_RULEBOOK_TEMPLATES: tuple[dict, ...] = (
    {
        "id": "0001",
        "slug": "nsm_rb_0001_template",
        "label": "Template 0001 — Full",
        "summary": "Zones, labels, addresses, services, actions, info.",
        "field_names": (
            "index",
            "status",
            "name",
            "source_zones",
            "destination_zones",
            "source_labels",
            "destination_labels",
            "source_addresses",
            "destination_addresses",
            "services_applications",
            "actions",
            "infos",
            "description",
        ),
    },
    {
        "id": "0002",
        "slug": "nsm_rb_0002_template",
        "label": "Template 0002 — Addresses only",
        "summary": "Addresses, services, actions, info.",
        "field_names": (
            "index",
            "status",
            "name",
            "source_addresses",
            "destination_addresses",
            "services_applications",
            "actions",
            "infos",
            "description",
        ),
    },
    {
        "id": "0003",
        "slug": "nsm_rb_0003_template",
        "label": "Template 0003 — Zones only",
        "summary": "Zones, services, actions, info.",
        "field_names": (
            "index",
            "status",
            "name",
            "source_zones",
            "destination_zones",
            "services_applications",
            "actions",
            "infos",
            "description",
        ),
    },
    {
        "id": "0004",
        "slug": "nsm_rb_0004_template",
        "label": "Template 0004 — Labels only",
        "summary": "Labels, services, actions, info.",
        "field_names": (
            "index",
            "status",
            "name",
            "source_labels",
            "destination_labels",
            "services_applications",
            "actions",
            "infos",
            "description",
        ),
    },
)

RULEBOOK_TEMPLATE_SLUGS = [spec["slug"] for spec in _RULEBOOK_TEMPLATES]
BUNDLED_RULEBOOK_TEMPLATE_SLUGS = RULEBOOK_TEMPLATE_SLUGS
RULEBOOK_TEMPLATE_BY_SLUG = {spec["slug"]: spec for spec in _RULEBOOK_TEMPLATES}

DEMO_RULEBOOK_SLUG = "nsm_rb_demo"
DEMO_RULEBOOK_TEMPLATE_SLUG = "nsm_rb_0003_template"


def _query_rulebook_template_cots():
    from django.db.utils import OperationalError, ProgrammingError
    from netbox_custom_objects.models import CustomObjectType

    try:
        return (
            CustomObjectType.objects.filter(group_name=RULEBOOK_TEMPLATE_GROUP)
            .order_by("slug")
        )
    except (ProgrammingError, OperationalError, ImportError):
        return CustomObjectType.objects.none()


def is_rulebook_template_slug(slug: str) -> bool:
    """Return True when *slug* is a rulebook blueprint (bundled or in template group)."""
    slug = (slug or "").strip()
    if not slug:
        return False
    if slug in RULEBOOK_TEMPLATE_BY_SLUG:
        return True
    try:
        return _query_rulebook_template_cots().filter(slug=slug).exists()
    except Exception:
        return slug.startswith("nsm_rb_") and slug.endswith("_template")


def get_rulebook_template_slugs() -> list[str]:
    """Return bundled template slugs plus any deployed templates in the template group."""
    slugs = list(RULEBOOK_TEMPLATE_SLUGS)
    try:
        extra = list(
            _query_rulebook_template_cots()
            .exclude(slug__in=slugs)
            .values_list("slug", flat=True)
        )
        slugs.extend(extra)
    except Exception:
        pass
    return slugs


def iter_rulebook_template_choices() -> list[tuple[str, str]]:
    """Return ``(slug, label)`` pairs for template selection forms."""
    choices: list[tuple[str, str]] = []
    for slug in get_rulebook_template_slugs():
        try:
            spec = get_template(slug)
        except KeyError:
            continue
        choices.append((slug, spec["label"]))
    return choices


def _spec_from_cot(cot) -> dict:
    field_names = tuple(
        field.name
        for field in cot.fields.all().order_by("weight", "schema_id", "name")
    )
    return {
        "id": cot.slug,
        "slug": cot.slug,
        "label": (cot.verbose_name or cot.name or cot.slug).strip(),
        "summary": (cot.description or cot.verbose_name or cot.name or cot.slug).strip(),
        "field_names": field_names,
        "source": "cot",
        "cot": cot,
    }


def get_template(slug: str) -> dict:
    slug = (slug or "").strip()
    if slug in RULEBOOK_TEMPLATE_BY_SLUG:
        return RULEBOOK_TEMPLATE_BY_SLUG[slug]
    try:
        cot = _query_rulebook_template_cots().filter(slug=slug).first()
    except Exception:
        cot = None
    if cot is not None:
        return _spec_from_cot(cot)
    raise KeyError(f"Unknown rulebook template slug: {slug!r}")


def is_deployed_rulebook_slug(slug: str) -> bool:
    """Return True for concrete rulebooks (``nsm_rb_<name>``), not templates."""
    return slug.startswith("nsm_rb_") and not is_rulebook_template_slug(slug)


def _fields_for_names(field_names: tuple[str, ...]) -> list[dict]:
    fields = []
    for name in field_names:
        field_def = deepcopy(_FIELD_CATALOG[name])
        group = rulebook_field_group_name(name)
        if group:
            field_def["group_name"] = group
        fields.append(field_def)
    return fields


def _allowed_object_labels(field_def: dict) -> list[str]:
    if field_def["type"] in ("integer", "boolean", "text", "longtext"):
        return []
    if field_def.get("related_object_type"):
        ref = field_def["related_object_type"]
        return [_OBJECT_TYPE_LABELS.get(ref, ref)]
    refs = field_def.get("related_object_types") or []
    return [_OBJECT_TYPE_LABELS.get(ref, ref) for ref in refs]


def _allowed_object_labels_from_cot_field(field) -> list[str]:
    from extras.choices import CustomFieldTypeChoices
    from netbox_custom_objects import constants

    if field.type in (
        CustomFieldTypeChoices.TYPE_INTEGER,
        CustomFieldTypeChoices.TYPE_BOOLEAN,
        CustomFieldTypeChoices.TYPE_TEXT,
        CustomFieldTypeChoices.TYPE_LONGTEXT,
    ):
        return []
    labels: list[str] = []
    if field.type == CustomFieldTypeChoices.TYPE_MULTIOBJECT:
        if field.is_polymorphic:
            for rot in field.related_object_types.all():
                if rot.app_label == constants.APP_LABEL:
                    m = constants.TABLE_MODEL_RE.match(rot.model)
                    if m:
                        from netbox_custom_objects.models import CustomObjectType

                        cot_slug = (
                            CustomObjectType.objects.filter(pk=int(m.group(1)))
                            .values_list("slug", flat=True)
                            .first()
                        )
                        if cot_slug:
                            labels.append(
                                _OBJECT_TYPE_LABELS.get(
                                    f"custom-objects/{cot_slug}",
                                    cot_slug,
                                )
                            )
                            continue
                labels.append(rot.model)
        elif field.related_object_type_id:
            rot = field.related_object_type
            if rot.app_label == constants.APP_LABEL:
                m = constants.TABLE_MODEL_RE.match(rot.model)
                if m:
                    from netbox_custom_objects.models import CustomObjectType

                    cot_slug = (
                        CustomObjectType.objects.filter(pk=int(m.group(1)))
                        .values_list("slug", flat=True)
                        .first()
                    )
                    if cot_slug:
                        labels.append(
                            _OBJECT_TYPE_LABELS.get(
                                f"custom-objects/{cot_slug}",
                                cot_slug,
                            )
                        )
                        return labels
            labels.append(rot.model)
    elif field.related_object_type_id:
        rot = field.related_object_type
        labels.append(rot.model)
    return labels


def _field_display_label_from_cot_field(field, *, cot=None) -> str:
    label = (field.label or field.name or "").strip()
    cot_obj = cot or getattr(field, "custom_object_type", None)
    group = resolve_group_name_for_display(field.group_name, cot=cot_obj)
    if label and group and group != label:
        return f"{label} ({group})"
    return label or group


def _field_display_label(field_def: dict, *, cot=None) -> str:
    """Combine field label and UI group for display, e.g. Zones (Source)."""
    label = (field_def.get("label") or "").strip()
    group = resolve_group_name_for_display(field_def.get("group_name"), cot=cot)
    if label and group and group != label:
        return f"{label} ({group})"
    return label or group


def template_wizard_columns(template_slug: str) -> list[dict]:
    """Simplified column rows for the rulebook creation wizard."""
    spec = get_template(template_slug)
    rows = []
    if spec.get("source") == "cot":
        cot = spec["cot"]
        for field in cot.fields.all().order_by("weight", "schema_id", "name"):
            rows.append(
                {
                    "name": field.name,
                    "label": _field_display_label_from_cot_field(field, cot=cot),
                    "allowed_objects": _allowed_object_labels_from_cot_field(field),
                    "required": bool(field.required),
                }
            )
        return rows
    for field_name in spec["field_names"]:
        field_def = _FIELD_CATALOG[field_name]
        rows.append(
            {
                "name": field_name,
                "label": _field_display_label(field_def),
                "allowed_objects": _allowed_object_labels(field_def),
                "required": bool(field_def.get("required")),
            }
        )
    return rows


def _fields_from_cot(cot) -> list[dict]:
    from netbox_custom_objects.schema.exporter import export_cot

    type_def = export_cot(cot)
    return list(type_def.get("fields") or [])


def _build_type_def(spec: dict) -> dict:
    template_id = spec["id"]
    slug = spec["slug"]
    return {
        "name": slug,
        "slug": slug,
        "verbose_name": f"Rulebook Template {template_id}",
        "verbose_name_plural": f"Rulebook Template {template_id}",
        "description": (
            f"NSM rulebook blueprint ({spec['summary']}). "
            "Not a rulebook — clone to nsm_rb_<name> to create one."
        ),
        "group_name": RULEBOOK_TEMPLATE_GROUP,
        "fields": _fields_for_names(spec["field_names"]),
        "removed_fields": [],
    }


def build_rulebook_template_type_defs() -> list[dict]:
    """Portable-schema type entries for all bundled rulebook templates."""
    return [_build_type_def(spec) for spec in _RULEBOOK_TEMPLATES]


def default_rulebook_description(template_slug: str) -> str:
    return f"NSM rulebook created from template {template_slug}."


def format_rulebook_display_name(name: str) -> str:
    """Return the default UI label for a rulebook: ``Rulebook <name>``."""
    label = (name or "").strip()
    if not label:
        return "Rulebook"
    return f"Rulebook {label}"


def normalize_rulebook_display_name(name: str) -> str:
    """Apply ``Rulebook <name>`` formatting without duplicating the prefix."""
    label = (name or "").strip()
    if not label:
        return format_rulebook_display_name("")
    if label.lower().startswith("rulebook "):
        return label
    return format_rulebook_display_name(label)


def build_rulebook_document(
    *,
    template_slug: str,
    rulebook_slug: str,
    verbose_name: str,
    verbose_name_plural: str | None = None,
    description: str | None = None,
) -> dict:
    """Build a portable-schema document for a concrete rulebook COT."""
    if not is_deployed_rulebook_slug(rulebook_slug):
        raise ValueError(
            f"Rulebook slug must match nsm_rb_<name> and not be a template: {rulebook_slug!r}"
        )
    spec = get_template(template_slug)
    display_name = verbose_name.strip()
    plural_name = (verbose_name_plural or display_name).strip()
    if spec.get("source") == "cot":
        fields = _fields_from_cot(spec["cot"])
    else:
        fields = _fields_for_names(spec["field_names"])
    return {
        "schema_version": "1",
        "types": [
            {
                "name": rulebook_slug,
                "slug": rulebook_slug,
                "verbose_name": display_name,
                "verbose_name_plural": plural_name,
                "description": description or default_rulebook_description(template_slug),
                "group_name": RULEBOOK_GROUP,
                "fields": fields,
                "removed_fields": [],
            }
        ],
    }
