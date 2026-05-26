"""
NSM YAML Bundle — serializer and deserializer.

Format: YAML (yaml.safe_load only — no Python code is executed).

Bundle structure example
------------------------
apiVersion: nsm/v1
kind: Bundle
metadata:
  generated: "2026-05-24T12:00:00Z"
  description: "My objects"
items:
  - apiVersion: nsm/v1
    kind: CustomType
    spec:
      name: addresses
      area: srcdst
      description: ""
      fields:
        - name: ipam_prefix
          label: Prefix
          type: object_ref
          model: ipam.Prefix
          selector: true
          tab_group: Address Parameters
        - name: dns_name
          label: DNS Name
          type: text
          tab_group: Address Parameters

  - apiVersion: nsm/v1
    kind: CustomObject
    spec:
      custom_type: addresses
      name: my-server
      description: ""
      fields:
        dns_name: "server.example.com"
        ipam_prefix:
          __model: ipam.Prefix
          __str: "10.0.0.0/24"
      table_data:
        - key: Owner
          value: John
"""

import datetime

import yaml
from django.apps import apps

BUNDLE_API_VERSION = "nsm/v1"
# Maximum bundle size to protect against DoS
_MAX_BUNDLE_BYTES = 1 * 1024 * 1024  # 1 MB

# Model-specific natural-key fields used during import to resolve object_ref values.
_NATURAL_KEY_FIELDS: dict[str, str] = {
    "ipam.prefix": "prefix",
    "ipam.ipaddress": "address",
    "ipam.iprange": "start_address",  # best approximation; may not be unique alone
    "dcim.device": "name",
    "dcim.interface": "name",
    "virtualization.virtualmachine": "name",
    "ipam.vlan": "name",
    "tenancy.tenant": "name",
    "netbox_nsm.securityzone": "name",
    "netbox_nsm.customprefix": "prefix",
}


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


def export_custom_type(ct) -> dict:
    """Serialize an ObjectCustomType instance to a bundle item dict."""
    return {
        "apiVersion": BUNDLE_API_VERSION,
        "kind": "CustomType",
        "spec": {
            "name": ct.name,
            "area": ct.area,
            "description": ct.description or "",
            "fields": ct.field_definitions or [],
        },
    }


def export_custom_object(obj) -> dict:
    """Serialize an ObjectCustomObject instance to a bundle item dict.

    object_ref values are stored as ``{__model: ..., __str: ...}`` so the
    importer can resolve them without touching arbitrary data.
    """
    field_defs = {fd["name"]: fd for fd in (obj.custom_type.field_definitions or []) if not fd.get("__meta__")}
    serialized_fields: dict = {}

    for key, value in obj.field_data.items():
        fd = field_defs.get(key, {})
        if fd.get("type") == "object_ref" and isinstance(value, dict) and "str" in value:
            serialized_fields[key] = {
                "__model": fd.get("model", ""),
                "__str": value["str"],
            }
        else:
            serialized_fields[key] = value

    return {
        "apiVersion": BUNDLE_API_VERSION,
        "kind": "CustomObject",
        "spec": {
            "custom_type": obj.custom_type.name,
            "name": obj.name,
            "description": obj.description or "",
            "fields": serialized_fields,
            "table_data": obj.table_data or [],
        },
    }


def build_bundle_yaml(items: list[dict], description: str = "") -> str:
    """Wrap a list of item dicts in a Bundle envelope and return YAML text."""
    bundle = {
        "apiVersion": BUNDLE_API_VERSION,
        "kind": "Bundle",
        "metadata": {
            "generated": datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "description": description,
        },
        "items": items,
    }
    return yaml.dump(bundle, allow_unicode=True, sort_keys=False, default_flow_style=False)


# ---------------------------------------------------------------------------
# Parse + validate
# ---------------------------------------------------------------------------


def parse_bundle(yaml_text: str) -> list[dict]:
    """Parse a YAML bundle string and return the list of item dicts.

    Raises ``ValueError`` with a human-readable message on any format error.
    Uses ``yaml.safe_load`` — no Python objects are instantiated.
    """
    if len(yaml_text.encode("utf-8")) > _MAX_BUNDLE_BYTES:
        raise ValueError(f"Bundle too large (max {_MAX_BUNDLE_BYTES // 1024} KB)")

    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Bundle must be a YAML mapping at the top level")

    api_ver = data.get("apiVersion")
    if api_ver != BUNDLE_API_VERSION:
        raise ValueError(
            f"Unsupported apiVersion {api_ver!r} (expected {BUNDLE_API_VERSION!r})"
        )

    kind = data.get("kind")
    if kind != "Bundle":
        raise ValueError(f"Expected kind=Bundle, got {kind!r}")

    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError("'items' must be a list")

    return items


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def _resolve_object_ref(model_str: str, ref_str: str):
    """Look up a model instance by its string representation.

    Returns the instance or ``None`` if it cannot be resolved.
    No code evaluation — only ORM queries.
    """
    if not model_str or not ref_str:
        return None
    try:
        model = apps.get_model(model_str)
    except (LookupError, ValueError):
        return None

    lookup_field = _NATURAL_KEY_FIELDS.get(model_str.lower())
    if lookup_field:
        try:
            return model.objects.get(**{lookup_field: ref_str})
        except Exception:
            pass

    # Generic fallback: try 'name'
    try:
        return model.objects.get(name=ref_str)
    except Exception:
        pass

    return None


def import_bundle(
    items: list[dict],
    update_existing: bool = False,
) -> tuple[list[str], list[str], list[str]]:
    """Import a list of bundle item dicts.

    Returns ``(created, updated, errors)`` — all lists of human-readable strings.

    Pass ``update_existing=True`` to overwrite objects that already exist.
    """
    from netbox_nsm.models import ObjectCustomType, ObjectCustomObject  # local import avoids circular refs

    created: list[str] = []
    updated: list[str] = []
    errors: list[str] = []
    type_cache: dict[str, ObjectCustomType] = {}

    # ---- Pass 1: CustomTypes ----
    for item in items:
        if not isinstance(item, dict) or item.get("kind") != "CustomType":
            continue
        spec = item.get("spec") or {}
        name = str(spec.get("name", "")).strip()
        if not name:
            errors.append("CustomType: missing 'name', skipped")
            continue

        area = spec.get("area", "srcdst")
        description = spec.get("description", "")
        fields = spec.get("fields", [])
        if not isinstance(fields, list):
            errors.append(f"CustomType {name!r}: 'fields' must be a list, skipped")
            continue

        try:
            ct, was_created = ObjectCustomType.objects.get_or_create(
                name=name,
                defaults={
                    "area": area,
                    "description": description,
                    "field_definitions": fields,
                },
            )
            if not was_created:
                if update_existing:
                    ct.area = area
                    ct.description = description
                    ct.field_definitions = fields
                    ct.save()
                    updated.append(f"CustomType: {name}")
                else:
                    errors.append(
                        f"CustomType {name!r} already exists — enable 'Update existing' to overwrite"
                    )
            else:
                created.append(f"CustomType: {name}")
            type_cache[name] = ct
        except Exception as exc:
            errors.append(f"CustomType {name!r}: {exc}")

    # Populate cache with DB types not in this bundle
    for ct in ObjectCustomType.objects.all():
        type_cache.setdefault(ct.name, ct)

    # ---- Pass 2: CustomObjects ----
    for item in items:
        if not isinstance(item, dict) or item.get("kind") != "CustomObject":
            continue
        spec = item.get("spec") or {}
        type_name = str(spec.get("custom_type", "")).strip()
        name = str(spec.get("name", "")).strip()

        if not type_name:
            errors.append(f"CustomObject {name!r}: missing 'custom_type', skipped")
            continue
        if not name:
            errors.append("CustomObject: missing 'name', skipped")
            continue

        ct = type_cache.get(type_name)
        if ct is None:
            errors.append(
                f"CustomObject {name!r}: custom_type {type_name!r} not found in DB, skipped"
            )
            continue

        # Resolve fields
        field_defs = {fd["name"]: fd for fd in (ct.field_definitions or []) if not fd.get("__meta__")}
        raw_fields = spec.get("fields") or {}
        field_data: dict = {}
        field_errors: list[str] = []

        for fname, fvalue in raw_fields.items():
            fd = field_defs.get(fname, {})
            if (
                fd.get("type") == "object_ref"
                and isinstance(fvalue, dict)
                and "__model" in fvalue
            ):
                instance = _resolve_object_ref(
                    fvalue.get("__model", ""), fvalue.get("__str", "")
                )
                if instance is None:
                    field_errors.append(
                        f"field {fname!r}: cannot resolve"
                        f" {fvalue.get('__model')} {fvalue.get('__str')!r}"
                    )
                    field_data[fname] = ""
                else:
                    field_data[fname] = {
                        "pk": instance.pk,
                        "url": instance.get_absolute_url(),
                        "str": str(instance),
                    }
            else:
                field_data[fname] = fvalue

        description = spec.get("description", "")
        table_data = spec.get("table_data") or []

        try:
            obj, was_created = ObjectCustomObject.objects.get_or_create(
                custom_type=ct,
                name=name,
                defaults={
                    "field_data": field_data,
                    "description": description,
                    "table_data": table_data,
                },
            )
            if not was_created:
                if update_existing:
                    obj.field_data = field_data
                    obj.description = description
                    obj.table_data = table_data
                    obj.save()
                    updated.append(f"CustomObject: {type_name}/{name}")
                else:
                    errors.append(
                        f"CustomObject {type_name}/{name!r} already exists —"
                        " enable 'Update existing' to overwrite"
                    )
            else:
                created.append(f"CustomObject: {type_name}/{name}")

            if field_errors:
                errors.extend(
                    f"CustomObject {type_name}/{name} — {e}" for e in field_errors
                )
        except Exception as exc:
            errors.append(f"CustomObject {type_name}/{name!r}: {exc}")

    return created, updated, errors
