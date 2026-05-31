"""Convert netbox_nsm BUILTIN_CUSTOM_TYPES into a portable schema document
for netbox-custom-objects and (optionally) seed default objects.

The mapping is intentionally lossy: netbox_nsm-specific UI hints
(``visible_when``, ``tab_group``, ``selector``, ``display_template``,
``__meta__`` markers) are dropped because they have no equivalent in the
portable schema spec. Type semantics that *do* exist map cleanly.
"""

import re

__all__ = (
    "build_schema_document",
    "build_choice_set_specs",
    "slugify_identifier",
    "iter_types",
    "type_slug",
)


# Areas that should be collapsed into a single combined section.
# ``source`` + ``destination`` -> ``srcdst`` (most NSM source/destination
# object types are symmetric).
_AREA_COLLAPSE = {
    "source": "srcdst",
    "destination": "srcdst",
}


def _collapse_area(area):
    a = slugify_identifier(area)
    return _AREA_COLLAPSE.get(a, a)


def type_slug(base_name):
    """``"Addresses"`` -> ``"nsm_addresses"``."""
    return f"nsm_{slugify_identifier(base_name)}"


def iter_types(builtin_types):
    """Yield ``(typedef, base_slug, prefixed_slug, areas)`` for every type.

    ``areas`` is a normalized list of (collapsed) area slugs.
    """
    for typedef in builtin_types:
        base_slug = slugify_identifier(typedef.get("name", ""))
        raw_areas = typedef.get("areas") or (
            [typedef.get("area")] if typedef.get("area") else []
        )
        areas = []
        for a in raw_areas:
            collapsed = _collapse_area(a)
            if collapsed and collapsed not in areas:
                areas.append(collapsed)
        yield typedef, base_slug, type_slug(base_slug), areas


_IDENT_CLEAN_RE = re.compile(r"[^a-z0-9]+")
_IDENT_COLLAPSE_RE = re.compile(r"_+")


def slugify_identifier(value):
    """Return a string matching ``^[a-z0-9]+(_[a-z0-9]+)*$``.

    Empty input becomes ``"x"`` so callers always get a legal identifier.
    """
    s = str(value or "").strip().lower()
    s = _IDENT_CLEAN_RE.sub("_", s)
    s = _IDENT_COLLAPSE_RE.sub("_", s).strip("_")
    return s or "x"


# Map netbox_nsm field types -> portable schema types.
_TYPE_MAP = {
    "text": "text",
    "markdown": "longtext",
    "number": "integer",
    "integer": "integer",
    "boolean": "boolean",
    "date": "date",
    "json": "json",
    "table": "json",
    "choice": "select",
    "object_ref": "object",
    "multiobject": "multiobject",
}


def _model_to_related_object_type(model_str):
    """``"dcim.Device"`` -> ``"dcim/device"``."""
    if not model_str or "." not in model_str:
        return None
    app, model = model_str.split(".", 1)
    return f"{app.lower()}/{model.lower()}"


def _choice_set_name(type_slug, field_slug):
    return f"nsm_{type_slug}_{field_slug}"


def build_choice_set_specs(builtin_types):
    """Collect every choice-set we need to create before applying the schema.

    Returns a list of dicts: ``{"name": str, "choices": list[str]}``.
    Deduplicated by name; later definitions for the same name win.
    """
    specs = {}
    for typedef in builtin_types:
        type_slug = slugify_identifier(typedef.get("name", ""))
        for field_def in typedef.get("field_definitions", []) or []:
            if not isinstance(field_def, dict) or field_def.get("__meta__"):
                continue
            if str(field_def.get("type", "")) != "choice":
                continue
            field_slug = slugify_identifier(field_def.get("name", ""))
            choices = [str(c) for c in (field_def.get("choices") or []) if str(c)]
            if not choices:
                continue
            specs[_choice_set_name(type_slug, field_slug)] = {
                "name": _choice_set_name(type_slug, field_slug),
                "choices": choices,
            }
    return list(specs.values())


def _build_field(field_def, type_slug, schema_id):
    """Return a portable schema field dict or ``None`` to skip this field."""
    if not isinstance(field_def, dict) or field_def.get("__meta__"):
        return None
    raw_type = str(field_def.get("type", "text"))
    schema_type = _TYPE_MAP.get(raw_type)
    if schema_type is None:
        return None

    name_slug = slugify_identifier(field_def.get("name", ""))
    if not name_slug:
        return None

    field = {
        "id": schema_id,
        "name": name_slug,
        "type": schema_type,
    }
    if field_def.get("label"):
        field["label"] = str(field_def["label"])
    if field_def.get("required"):
        field["required"] = True
    if field_def.get("description"):
        field["description"] = str(field_def["description"])[:200]
    if field_def.get("group_name"):
        field["group_name"] = str(field_def["group_name"])
    if field_def.get("weight") is not None:
        field["weight"] = int(field_def["weight"])

    if schema_type == "select":
        field["choice_set"] = _choice_set_name(
            type_slug, slugify_identifier(field_def.get("name", ""))
        )

    if schema_type in ("object", "multiobject"):
        rot = _model_to_related_object_type(field_def.get("model", ""))
        if not rot:
            return None
        field["related_object_type"] = rot

    return field


def build_schema_document(builtin_types):
    """Convert BUILTIN_CUSTOM_TYPES into a portable schema document.

    Emits one CustomObjectType per typedef. Slug is prefixed with ``nsm_``
    (e.g. ``nsm_addresses``). Area membership is expressed via
    NSMSection.custom_object_types M2M, with ``source``+``destination``
    collapsed into ``srcdst``.
    """
    types = []
    for typedef, base_slug, slug, areas in iter_types(builtin_types):
        type_name = slug
        verbose_name = str(typedef.get("name", "")) or base_slug
        # All NSM types are grouped under the single "NSM" UI group; the
        # per-instance "area" multi-object field tells you *which* role(s)
        # the object plays.
        group_name = "NSM"

        fields = []
        # Auto-injected fields with STABLE, fixed IDs:
        #   id=1  name        (primary, required)
        #   id=3  description (text)
        #   id=6  comments    (longtext)
        #   id=7  color       (text)
        # IDs 2, 4, 5 are intentionally not used (slug / owner_group / owner
        # are NOT auto-injected — add them in field_definitions when needed).

        # Collect user-defined field names to avoid shadowing them.
        user_field_names = {
            slugify_identifier(fd.get("name", ""))
            for fd in (typedef.get("field_definitions") or [])
            if isinstance(fd, dict) and not fd.get("__meta__") and fd.get("name")
        }

        fields.append({"id": 1, "name": "name", "type": "text", "label": "Name",
                        "primary": True, "required": True})

        if "description" not in user_field_names:
            fields.append({"id": 3, "name": "description", "type": "text",
                           "label": "Description"})

        if "comments" not in user_field_names:
            fields.append({"id": 6, "name": "comments", "type": "longtext",
                           "label": "Comments", "group_name": "Comments"})

        if "color" not in user_field_names:
            fields.append({"id": 7, "name": "color", "type": "text",
                           "label": "Color"})

        # Note: ``order_id``, ``area`` and ``display_template`` are *type-level*
        # concepts and live on NSMTypeConfig / NSMSection — they are NOT
        # injected as per-instance fields.

        # User-defined fields start at id 100 to leave headroom for future
        # default-injected fields without colliding.
        schema_id = 100
        for field_def in typedef.get("field_definitions", []) or []:
            built = _build_field(field_def, base_slug, schema_id)
            if built is None:
                continue
            fields.append(built)
            schema_id += 1

        types.append(
            {
                "name": type_name,
                "slug": slug,
                "verbose_name": verbose_name,
                "verbose_name_plural": verbose_name,
                "description": str(typedef.get("description", ""))[:200],
                "group_name": group_name,
                "fields": fields,
                "removed_fields": [],
            }
        )

    return {"schema_version": "1", "types": types}
