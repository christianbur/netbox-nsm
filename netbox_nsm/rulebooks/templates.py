"""Rulebook template definitions for NSM Custom-Object rulebooks.

Templates are deployed as ``CustomObjectType`` rows in group **NSM Rulebook
Templates** (slugs ``nsm_rb_0001_template``, …). They are blueprints only.

Concrete rulebooks use slugs ``nsm_rb_<name>`` in group **NSM Rulebooks** and
are created by cloning a template schema via ``build_rulebook_document``.
"""

from __future__ import annotations

from copy import deepcopy

from netbox_nsm.rulebooks.rulebook_groups import resolve_group_name_for_display

__all__ = (
    "BUNDLED_RULEBOOK_TEMPLATE_SLUGS",
    "DEFAULT_RULEBOOK_SCHEMA_YAML",
    "DEMO_RULEBOOK_SCHEMA_YAML",
    "DEMO_RULEBOOK_SLUG",
    "DEMO_ZONE_MATRIX_RULEBOOK_SLUG",
    "SCHEMA_DEMO_RULEBOOK_SLUG",
    "RULEBOOK_GROUP",
    "RULEBOOK_TEMPLATE_GROUP",
    "RULEBOOK_TEMPLATE_SLUGS",
    "RULEBOOK_TEMPLATE_BY_SLUG",
    "build_rulebook_document",
    "build_rulebook_document_from_schema",
    "BENCH_RULEBOOK_FIELD_NAMES",
    "build_rulebook_template_type_defs",
    "bench_rulebook_schema_yaml",
    "default_rulebook_schema_yaml",
    "demo_rulebook_schema_yaml",
    "schema_demo_rulebook_schema_yaml",
    "export_rulebook_schema_yaml_for_copy",
    "extract_rulebook_wizard_metadata_from_schema_yaml",
    "resolve_rulebook_schema_yaml_for_validation",
    "validate_substituted_rulebook_schema_yaml",
    "substitute_rulebook_schema_placeholders",
    "format_rulebook_display_name",
    "get_rulebook_template_slugs",
    "iter_rulebook_template_choices",
    "normalize_rulebook_display_name",
    "get_template",
    "is_deployed_rulebook_slug",
    "is_rulebook_template_slug",
    "parse_rulebook_schema_yaml",
    "template_wizard_columns",
    "wizard_columns_from_fields",
    "wizard_columns_from_schema_yaml",
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
    },
    "status": {
        "id": 2,
        "name": "status",
        "type": "boolean",
        "label": "Status",
        "description": "When false, the rule is disabled.",
        "required": False,
        "weight": 2,
    },
    "name": {
        "id": 3,
        "name": "name",
        "type": "text",
        "label": "Name",
        "description": "Optional short rule name.",
        "required": False,
        "weight": 3,
    },
    "source": {
        "id": 4,
        "name": "source",
        "type": "multiobject",
        "label": "Source",
        "description": "Source objects: zones, labels, addresses, and address groups.",
        "required": True,
        "weight": 11,
        "is_polymorphic": True,
        "related_object_types": [
            "custom-objects/nsm_zone",
            "custom-objects/nsm_label",
            "custom-objects/nsm_address",
            "custom-objects/nsm_address_custom",
            "custom-objects/nsm_address_group",
        ],
    },
    "destination": {
        "id": 5,
        "name": "destination",
        "type": "multiobject",
        "label": "Destination",
        "description": "Destination objects: zones, labels, addresses, and address groups.",
        "required": True,
        "weight": 21,
        "is_polymorphic": True,
        "related_object_types": [
            "custom-objects/nsm_zone",
            "custom-objects/nsm_label",
            "custom-objects/nsm_address",
            "custom-objects/nsm_address_custom",
            "custom-objects/nsm_address_group",
        ],
    },
    "source_zones": {
        "id": 4,
        "name": "source_zones",
        "type": "multiobject",
        "label": "Zones",
        "description": "Source objects: zones",
        "required": True,
        "weight": 11,
        "is_polymorphic": True,
        "related_object_types": ["custom-objects/nsm_zone"],
    },
    "destination_zones": {
        "id": 14,
        "name": "destination_zones",
        "type": "multiobject",
        "label": "Zones",
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
        "description": "Source objects: addresses and address groups",
        "required": True,
        "weight": 13,
        "is_polymorphic": True,
        "related_object_types": [
            "custom-objects/nsm_address",
            "custom-objects/nsm_address_custom",
            "custom-objects/nsm_address_group",
        ],
    },
    "destination_addresses": {
        "id": 7,
        "name": "destination_addresses",
        "type": "multiobject",
        "label": "Addresses",
        "description": "Destination objects: addresses and address groups",
        "required": True,
        "weight": 23,
        "is_polymorphic": True,
        "related_object_types": [
            "custom-objects/nsm_address",
            "custom-objects/nsm_address_custom",
            "custom-objects/nsm_address_group",
        ],
    },
    "services_applications": {
        "id": 8,
        "name": "services_applications",
        "type": "multiobject",
        "label": "Services & Applications",
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
        "description": "Free-text rule description.",
        "required": False,
        "weight": 100,
    },
}

_OBJECT_TYPE_LABELS: dict[str, str] = {
    "custom-objects/nsm_zone": "Zone",
    "custom-objects/nsm_label": "Label",
    "custom-objects/nsm_address": "Address",
    "custom-objects/nsm_address_custom": "Address Custom",
    "custom-objects/nsm_address_group": "Address Group",
    "custom-objects/nsm_service": "Service",
    "custom-objects/nsm_service_group": "Service Group",
    "custom-objects/nsm_app_network": "Network App",
    "custom-objects/nsm_action": "Action",
    "custom-objects/nsm_app_business": "Business App",
}

_RULEBOOK_TEMPLATES: tuple[dict, ...] = ()

RULEBOOK_TEMPLATE_SLUGS = [spec["slug"] for spec in _RULEBOOK_TEMPLATES]
BUNDLED_RULEBOOK_TEMPLATE_SLUGS = RULEBOOK_TEMPLATE_SLUGS
RULEBOOK_TEMPLATE_BY_SLUG = {spec["slug"]: spec for spec in _RULEBOOK_TEMPLATES}

SCHEMA_DEMO_RULEBOOK_SLUG = "nsm_rb_demo_rulebook"
DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG = "nsm_rb_demo_zone_addresses"
DEMO_ZONE_MATRIX_RULEBOOK_SLUG = "nsm_rb_demo_zone_matrix"
DEMO_RULEBOOK_SLUG = DEMO_ZONE_MATRIX_RULEBOOK_SLUG

DEFAULT_RULEBOOK_SCHEMA_YAML = """schema_version: "1"
types:
  - name: nsm_rb_{{name}}
    slug: nsm_rb_{{name}}
    verbose_name: "{{display_name}}"
    verbose_name_plural: "{{display_name}}"
    description: "{{description}}"
    group_name: NSM Rulebooks
    fields:
      - id: 1
        name: index
        type: integer
        label: Index
        required: true
        weight: 1
        primary: true
      - id: 2
        name: status
        type: boolean
        label: Status
        required: false
        weight: 2
      - id: 3
        name: name
        type: text
        label: Name
        required: true
        weight: 3
      - id: 4
        name: source
        type: multiobject
        label: Source
        required: true
        weight: 11
        is_polymorphic: true
        related_object_types:
          - custom-objects/nsm_zone
          - custom-objects/nsm_label
          - custom-objects/nsm_address
          - custom-objects/nsm_address_custom
          - custom-objects/nsm_address_group
      - id: 5
        name: destination
        type: multiobject
        label: Destination
        required: true
        weight: 21
        is_polymorphic: true
        related_object_types:
          - custom-objects/nsm_zone
          - custom-objects/nsm_label
          - custom-objects/nsm_address
          - custom-objects/nsm_address_custom
          - custom-objects/nsm_address_group
      - id: 8
        name: services_applications
        type: multiobject
        label: Services & Applications
        required: true
        weight: 40
        is_polymorphic: true
        related_object_types:
          - custom-objects/nsm_service
          - custom-objects/nsm_service_group
          - custom-objects/nsm_app_network
      - id: 9
        name: actions
        type: multiobject
        label: Actions
        required: true
        weight: 50
        related_object_type: custom-objects/nsm_action
      - id: 10
        name: infos
        type: multiobject
        label: Infos
        required: false
        weight: 60
        related_object_type: custom-objects/nsm_app_business
      - id: 11
        name: description
        type: longtext
        label: Description
        required: false
        weight: 100
    removed_fields: []
"""

DEMO_RULEBOOK_SCHEMA_YAML = """schema_version: "1"
types:
  - name: nsm_rb_{{name}}
    slug: nsm_rb_{{name}}
    verbose_name: "{{display_name}}"
    verbose_name_plural: "{{display_name}}"
    description: "{{description}}"
    group_name: NSM Rulebooks
    fields:
      - id: 1
        name: index
        type: integer
        label: Index
        required: true
        weight: 1
        primary: true
      - id: 2
        name: status
        type: boolean
        label: Status
        required: false
        weight: 2
      - id: 3
        name: name
        type: text
        label: Name
        required: true
        weight: 3
      - id: 4
        name: source
        type: multiobject
        label: Source
        required: true
        weight: 11
        is_polymorphic: true
        related_object_types:
          - custom-objects/nsm_zone
      - id: 5
        name: destination
        type: multiobject
        label: Destination
        required: true
        weight: 21
        is_polymorphic: true
        related_object_types:
          - custom-objects/nsm_zone
      - id: 9
        name: actions
        type: multiobject
        label: Actions
        required: true
        weight: 50
        related_object_type: custom-objects/nsm_action
      - id: 11
        name: description
        type: longtext
        label: Description
        required: false
        weight: 100
    removed_fields: []
"""

def default_rulebook_schema_yaml() -> str:
    """Return the default editable YAML schema for the rulebook add wizard."""
    return DEFAULT_RULEBOOK_SCHEMA_YAML


_SCHEMA_YAML_PLACEHOLDER_TOKENS = (
    "{{name}}",
    "{{display_name}}",
    "{{description}}",
)


def _schema_yaml_value_is_literal(value: str) -> bool:
    text = str(value or "")
    if not text.strip():
        return False
    return not any(token in text for token in _SCHEMA_YAML_PLACEHOLDER_TOKENS)


def _rulebook_name_from_schema_slug(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("nsm_rb_"):
        return text[len("nsm_rb_") :]
    return text


def extract_rulebook_wizard_metadata_from_schema_yaml(text: str) -> dict[str, str]:
    """Read concrete rulebook metadata from wizard YAML (no template placeholders)."""
    import yaml

    raw = (text or "").strip()
    if not raw:
        return {}
    try:
        document = yaml.safe_load(raw)
    except yaml.YAMLError:
        return {}
    if not isinstance(document, dict):
        return {}
    types = document.get("types")
    if not isinstance(types, list) or not types:
        return {}
    type_def = types[0]
    if not isinstance(type_def, dict):
        return {}

    result: dict[str, str] = {}
    slug = str(type_def.get("slug") or type_def.get("name") or "").strip()
    if _schema_yaml_value_is_literal(slug):
        name = _rulebook_name_from_schema_slug(slug)
        if name:
            result["name"] = name

    verbose_name = str(type_def.get("verbose_name") or "").strip()
    if _schema_yaml_value_is_literal(verbose_name):
        result["verbose_name"] = verbose_name

    if "description" in type_def:
        description = str(type_def.get("description") or "").strip()
        if _schema_yaml_value_is_literal(str(type_def.get("description") or "")):
            result["description"] = description
    return result


_SCHEMA_VALIDATE_FALLBACK_NAME = "preview"
_SCHEMA_VALIDATE_FALLBACK_DISPLAY = "Schema Preview"


def resolve_rulebook_schema_yaml_for_validation(
    text: str,
    *,
    display_name: str = "",
    name: str = "",
    description: str = "",
) -> str:
    """Substitute wizard placeholders before schema validation."""
    preview_name = (name or "").strip()
    preview_display = (display_name or "").strip()
    preview_description = (description or "").strip()
    raw = text or ""
    if any(
        token in raw
        for token in _SCHEMA_YAML_PLACEHOLDER_TOKENS
    ):
        if not preview_name and not preview_display:
            preview_name = _SCHEMA_VALIDATE_FALLBACK_NAME
        if not preview_display:
            preview_display = _SCHEMA_VALIDATE_FALLBACK_DISPLAY
    return substitute_rulebook_schema_placeholders(
        raw,
        display_name=preview_display,
        name=preview_name,
        description=preview_description,
    )


def validate_substituted_rulebook_schema_yaml(
    text: str,
    *,
    display_name: str = "",
    name: str = "",
    description: str = "",
) -> None:
    """Validate portable-schema YAML using existing parser (no custom logic)."""
    resolved = resolve_rulebook_schema_yaml_for_validation(
        text,
        display_name=display_name,
        name=name,
        description=description,
    )
    parse_rulebook_schema_yaml(resolved)


def substitute_rulebook_schema_placeholders(
    text: str,
    *,
    display_name: str = "",
    name: str = "",
    description: str = "",
) -> str:
    """Replace ``{{display_name}}``, ``{{name}}``, and ``{{description}}`` in wizard YAML."""
    from netbox_nsm.rulebooks.create import (
        derive_rulebook_name,
        normalize_rulebook_display_name,
    )

    raw_display = (display_name or "").strip()
    slug_name = (name or "").strip()
    if not slug_name and raw_display:
        slug_name = derive_rulebook_name(raw_display)
    resolved_display = (
        normalize_rulebook_display_name(raw_display) if raw_display else ""
    )
    resolved_description = (description or "").strip()
    replacements = {
        "{{display_name}}": resolved_display,
        "{{name}}": slug_name,
        "{{description}}": resolved_description,
    }
    result = text or ""
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result


def demo_rulebook_schema_yaml() -> str:
    """Return resolved portable-schema YAML for the starter demo rulebook."""
    return substitute_rulebook_schema_placeholders(
        DEMO_RULEBOOK_SCHEMA_YAML,
        display_name="RB Demo Zone Matrix",
        name="demo_zone_matrix",
        description=(
            "Demo rulebook for zone-matrix evaluation (30×30); "
            "populated by bundle nsm_demo_zone_matrix."
        ),
    )


def schema_demo_rulebook_schema_yaml() -> str:
    """Resolved portable-schema YAML for ``nsm_rb_demo_rulebook`` (NSM Schema starter)."""
    import yaml

    raw = yaml.dump(
        _bench_rulebook_schema_document(),
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).strip() + "\n"
    return substitute_rulebook_schema_placeholders(
        raw,
        display_name="RB Demo Rulebook",
        name="demo_rulebook",
        description=(
            "Starter rulebook shipped with NSM Schema "
            "(zones, addresses, and address groups)."
        ),
    )


BENCH_RULEBOOK_FIELD_NAMES = (
    "index",
    "status",
    "name",
    "source_zones",
    "destination_zones",
    "source_addresses",
    "destination_addresses",
    "services_applications",
    "actions",
)


def _bench_rulebook_schema_document() -> dict:
    return {
        "schema_version": "1",
        "types": [
            {
                "name": "nsm_rb_{{name}}",
                "slug": "nsm_rb_{{name}}",
                "verbose_name": "{{display_name}}",
                "verbose_name_plural": "{{display_name}}",
                "description": "{{description}}",
                "group_name": RULEBOOK_GROUP,
                "fields": _fields_for_names(BENCH_RULEBOOK_FIELD_NAMES),
                "removed_fields": [],
            }
        ],
    }


def bench_rulebook_schema_yaml() -> str:
    """Resolved portable-schema YAML for ``nsm_rb_demo_zone_addresses`` (zones + addresses)."""
    import yaml

    raw = yaml.dump(
        _bench_rulebook_schema_document(),
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).strip() + "\n"
    return substitute_rulebook_schema_placeholders(
        raw,
        display_name="RB Demo Zone/Address",
        name="demo_zone_addresses",
        description=(
            "Zone, address, and address-group bench (5k hosts, 50k-scale groups/rules). "
            "Fill with the RB Demo Zone/Address setup job."
        ),
    )


def export_rulebook_schema_yaml_for_copy(cot) -> str:
    """Portable-schema YAML for clipboard copy (paste into Add Rulebook wizard)."""
    import yaml

    from netbox_custom_objects.schema.exporter import export_cot

    type_def = export_cot(cot)
    document = {
        "schema_version": "1",
        "types": [
            {
                "name": "nsm_rb_{{name}}",
                "slug": "nsm_rb_{{name}}",
                "verbose_name": "{{display_name}}",
                "verbose_name_plural": "{{display_name}}",
                "description": "{{description}}",
                "group_name": RULEBOOK_GROUP,
                "fields": list(type_def.get("fields") or []),
                "removed_fields": list(type_def.get("removed_fields") or []),
            }
        ],
    }
    return yaml.dump(
        document,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).strip() + "\n"


def parse_rulebook_schema_yaml(text: str) -> dict:
    """Parse and validate portable-schema YAML for rulebook creation."""
    import yaml
    from django.core.exceptions import ValidationError
    from django.utils.translation import gettext_lazy as _

    raw = (text or "").strip()
    if not raw:
        raise ValidationError(_("Enter a rulebook schema."))

    try:
        document = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValidationError(_("Invalid YAML: %(error)s") % {"error": exc}) from exc

    if not isinstance(document, dict):
        raise ValidationError(_("Schema must be a YAML mapping."))
    if document.get("schema_version") != "1":
        raise ValidationError(_("schema_version must be '1'."))

    types = document.get("types")
    if not isinstance(types, list) or not types:
        raise ValidationError(_("Schema must contain at least one type in types."))

    type_def = types[0]
    if not isinstance(type_def, dict):
        raise ValidationError(_("The first type entry must be a mapping."))

    fields = type_def.get("fields")
    if not isinstance(fields, list) or not fields:
        raise ValidationError(_("Schema type must define at least one field."))

    field_names: set[str] = set()
    for index, field_def in enumerate(fields):
        if not isinstance(field_def, dict):
            raise ValidationError(
                _("Field %(index)s must be a mapping.") % {"index": index + 1}
            )
        name = (field_def.get("name") or "").strip()
        if not name:
            raise ValidationError(
                _("Field %(index)s is missing name.") % {"index": index + 1}
            )
        if name in field_names:
            raise ValidationError(
                _("Duplicate field name: %(name)s.") % {"name": name}
            )
        field_names.add(name)
        field_type = (field_def.get("type") or "").strip()
        if not field_type:
            raise ValidationError(
                _("Field %(name)s is missing type.") % {"name": name}
            )

    return type_def


def wizard_columns_from_fields(fields: list[dict]) -> list[dict]:
    """Build wizard preview rows from portable-schema field definitions."""
    rows = []
    for field_def in fields:
        rows.append(
            {
                "name": field_def["name"],
                "label": _field_display_label(field_def),
                "allowed_objects": _allowed_object_labels(field_def),
                "required": bool(field_def.get("required")),
            }
        )
    return rows


def wizard_columns_from_schema_yaml(text: str) -> list[dict]:
    """Parse *text* and return wizard preview rows."""
    type_def = parse_rulebook_schema_yaml(text)
    return wizard_columns_from_fields(list(type_def.get("fields") or []))


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
    if slug.startswith("nsm_rb_") and slug.endswith("_template"):
        return True
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
    """Return True when *slug* belongs to a concrete rulebook COT (``role: rulebook``)."""
    from netbox_custom_objects.models import CustomObjectType
    from netbox_nsm.rulebooks.registry import is_deployed_rulebook_cot

    cot = CustomObjectType.objects.filter(slug=slug).first()
    if cot is not None:
        return is_deployed_rulebook_cot(cot)
    return slug.startswith("nsm_rb_") and not is_rulebook_template_slug(slug)


def _fields_for_names(field_names: tuple[str, ...]) -> list[dict]:
    return [deepcopy(_FIELD_CATALOG[name]) for name in field_names]


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


def resolve_rulebook_cot_description(
    *,
    description: str | None,
    schema_type_def: dict,
    rulebook_slug: str,
    display_name: str = "",
    name: str = "",
) -> str:
    """Pick the COT description and resolve wizard placeholders."""
    explicit = (description or "").strip()
    if explicit:
        return explicit

    schema_desc = substitute_rulebook_schema_placeholders(
        (schema_type_def.get("description") or "").strip(),
        display_name=display_name,
        name=name,
        description=explicit,
    ).strip()
    if schema_desc:
        return schema_desc

    return default_rulebook_description(rulebook_slug)


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


def build_rulebook_document_from_schema(
    *,
    schema_type_def: dict,
    rulebook_slug: str,
    verbose_name: str,
    verbose_name_plural: str | None = None,
    description: str | None = None,
    name: str = "",
) -> dict:
    """Build a portable-schema document for a concrete rulebook from parsed YAML."""
    if not is_deployed_rulebook_slug(rulebook_slug):
        raise ValueError(
            f"Rulebook slug must match nsm_rb_<name> and not be a template: {rulebook_slug!r}"
        )
    display_name = verbose_name.strip()
    plural_name = (verbose_name_plural or display_name).strip()
    fields = list(schema_type_def.get("fields") or [])
    name_segment = (name or "").strip()
    if not name_segment and rulebook_slug.startswith("nsm_rb_"):
        name_segment = rulebook_slug[len("nsm_rb_") :]
    resolved_description = resolve_rulebook_cot_description(
        description=description,
        schema_type_def=schema_type_def,
        rulebook_slug=rulebook_slug,
        display_name=display_name,
        name=name_segment,
    )
    return {
        "schema_version": "1",
        "types": [
            {
                "name": rulebook_slug,
                "slug": rulebook_slug,
                "verbose_name": display_name,
                "verbose_name_plural": plural_name,
                "description": resolved_description,
                "group_name": RULEBOOK_GROUP,
                "fields": fields,
                "removed_fields": list(schema_type_def.get("removed_fields") or []),
            }
        ],
    }


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
