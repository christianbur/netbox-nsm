"""Schema-inference contract for NSM Custom Object Types (Phase B).

The platform must react to *structure* (deployed ``CustomObjectTypeField``
schema) and optional ``role`` metadata — never to hardcoded field names like
``address`` or ``group``. This module is the single source of truth analyzers
and address helpers consult.

Inference rules (see ``docs/MODULAR_ARCHITECTURE_PLAN.md``):

* ``object``/``multiobject`` field whose ``related_object_types`` are
  **exclusively** IPAM models → that field is the IPAM binding; the COT has
  role ``address``.
* ``multiobject`` field whose targets are address-role COTs → members field;
  the COT has role ``address_group``.
* ``role`` in COT ``comments`` (or slug default) overrides inference.

Field names are irrelevant: GFK columns are derived as
``{field.name}_content_type_id`` / ``{field.name}_object_id``.
"""

from __future__ import annotations

from typing import Iterator

__all__ = (
    "resolve_role",
    "iter_cots_by_role",
    "resolve_ipam_field",
    "resolve_ipam_field_name",
    "ipam_gfk_attrs",
    "resolve_members_field",
    "resolve_members_field_name",
    "membership_through",
    "is_universal_address",
    "resolve_literal_network",
    "cot_for_content_type",
)

_IPAM_APP_LABEL = "ipam"
_IPAM_MODELS = frozenset({"ipaddress", "prefix", "iprange"})
_CUSTOM_ADDRESS_FIELDS = frozenset({"ipv4", "ipv6", "subnet"})
_UNIVERSAL_NETWORKS = frozenset({"0.0.0.0/0", "::/0"})

# Default GFK field name when a COT exposes no resolvable IPAM field.
_DEFAULT_IPAM_FIELD = "address"


# --------------------------------------------------------------------------- #
# Low-level field/content-type helpers
# --------------------------------------------------------------------------- #
def _object_field_types() -> set:
    from extras.choices import CustomFieldTypeChoices

    return {
        CustomFieldTypeChoices.TYPE_OBJECT,
        CustomFieldTypeChoices.TYPE_MULTIOBJECT,
    }


def _multiobject_type():
    from extras.choices import CustomFieldTypeChoices

    return CustomFieldTypeChoices.TYPE_MULTIOBJECT


def _iter_object_fields(cot):
    try:
        from netbox_custom_objects.models import CustomObjectTypeField
    except ImportError:
        return []
    return list(
        CustomObjectTypeField.objects.filter(
            custom_object_type=cot, type__in=_object_field_types()
        )
    )


def _related_content_types(field) -> list:
    types: list = []
    related = getattr(field, "related_object_type", None)
    if related is not None:
        types.append(related)
    try:
        types.extend(list(field.related_object_types.all()))
    except Exception:
        pass
    return types


def _content_type_is_ipam(ct) -> bool:
    return (
        getattr(ct, "app_label", None) == _IPAM_APP_LABEL
        and getattr(ct, "model", None) in _IPAM_MODELS
    )


def _field_targets_only_ipam(field) -> bool:
    related = _related_content_types(field)
    if not related:
        return False
    return all(_content_type_is_ipam(ct) for ct in related)


def cot_for_content_type(ct):
    """Return the ``CustomObjectType`` a related ContentType points at, or None."""
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return None
    model = getattr(ct, "model", None)
    if not model:
        return None
    return CustomObjectType.objects.filter(slug=model).first()


def _model_field_names(model) -> set[str]:
    meta = getattr(model, "_meta", None)
    if meta is None:
        return set()
    return {field.name for field in meta.get_fields()}


def _cot_has_literal_address_fields(cot) -> bool:
    try:
        model = cot.get_model()
    except Exception:
        return False
    return _CUSTOM_ADDRESS_FIELDS.issubset(_model_field_names(model))


def _cot_looks_like_address(cot) -> bool:
    if cot is None:
        return False
    if resolve_ipam_field(cot) is not None:
        return True
    return _cot_has_literal_address_fields(cot)


# --------------------------------------------------------------------------- #
# IPAM (address) field resolution
# --------------------------------------------------------------------------- #
def resolve_ipam_field(cot):
    """Return the COT field that binds to IPAM objects, or ``None``.

    Inference is structural: the first ``object``/``multiobject`` field whose
    ``related_object_types`` are exclusively IPAM models.
    """
    if cot is None:
        return None
    for field in _iter_object_fields(cot):
        if _field_targets_only_ipam(field):
            return field
    return None


def resolve_ipam_field_name(cot) -> str:
    """Return the IPAM field name (falls back to ``address``)."""
    field = resolve_ipam_field(cot)
    name = getattr(field, "name", None)
    return name or _DEFAULT_IPAM_FIELD


def ipam_gfk_attrs(cot) -> tuple[str, str]:
    """Return ``(content_type_attr, object_id_attr)`` for the IPAM GFK columns."""
    name = resolve_ipam_field_name(cot)
    return f"{name}_content_type_id", f"{name}_object_id"


# --------------------------------------------------------------------------- #
# Address-group (members) field resolution
# --------------------------------------------------------------------------- #
def resolve_members_field(cot):
    """Return the multiobject field collecting address members, or ``None``."""
    if cot is None:
        return None
    multi = _multiobject_type()
    for field in _iter_object_fields(cot):
        if getattr(field, "type", None) != multi:
            continue
        related = _related_content_types(field)
        if not related:
            continue
        for ct in related:
            target = cot_for_content_type(ct)
            if target is not None and _cot_looks_like_address(target):
                return field
    return None


def resolve_members_field_name(cot) -> str:
    field = resolve_members_field(cot)
    return getattr(field, "name", None) or "group"


def membership_through(group_cot):
    """Return ``(ThroughModel, group_fk_name, member_fk_name)`` for the M2M.

    Field names are resolved dynamically; the through table name is data-driven.
    """
    if group_cot is None:
        return None, None, None
    field = resolve_members_field(group_cot)
    if field is None:
        return None, None, None
    try:
        from django.apps import apps
        from netbox_custom_objects import constants

        through = apps.get_model(constants.APP_LABEL, field.through_model_name)
    except Exception:
        return None, None, None

    try:
        group_model = group_cot.get_model()
    except Exception:
        return None, None, None

    group_field = member_field = None
    for fk in through._meta.concrete_fields:
        related = getattr(fk, "related_model", None)
        if related is None:
            continue
        if related is group_model:
            group_field = fk.name
        else:
            member_field = fk.name
    if not group_field or not member_field:
        return None, None, None
    return through, group_field, member_field


# --------------------------------------------------------------------------- #
# Role resolution
# --------------------------------------------------------------------------- #
def resolve_role(cot) -> str | None:
    """Return the effective semantic role for *cot*.

    Order: explicit ``role`` in comments → slug default → structural inference.
    """
    if cot is None:
        return None
    try:
        from netbox_nsm.type_metadata.roles import resolve_role_for_cot

        explicit = resolve_role_for_cot(cot)
    except Exception:
        explicit = None
    if explicit:
        return explicit

    if resolve_ipam_field(cot) is not None or _cot_has_literal_address_fields(cot):
        return "address"
    if resolve_members_field(cot) is not None:
        return "address_group"
    return None


def iter_cots_by_role(role: str) -> Iterator:
    """Yield every deployed COT whose resolved role equals *role*."""
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return
    for cot in CustomObjectType.objects.all():
        if resolve_role(cot) == role:
            yield cot


# --------------------------------------------------------------------------- #
# Literal / universal address ("ANY")
# --------------------------------------------------------------------------- #
def resolve_literal_network(obj) -> str | None:
    """Return the literal CIDR for an address object (IPAM-free), or ``None``."""
    from netbox_nsm.addresses.address_literal import get_policy_address_cidr

    return get_policy_address_cidr(obj)


def is_universal_address(obj) -> bool:
    """True when an address object represents ANY (``0.0.0.0/0`` / ``::/0``)."""
    import ipaddress

    cidr = resolve_literal_network(obj)
    if not cidr:
        return False
    try:
        normalized = str(ipaddress.ip_network(cidr, strict=False))
    except ValueError:
        return cidr in _UNIVERSAL_NETWORKS
    return normalized in _UNIVERSAL_NETWORKS
