"""Shared TypeConfig definitions for Setup, sync, and demos."""

__all__ = (
    "REQUIRED_COT_SLUGS",
    "RULEBOOK_TEMPLATE_SLUGS",
    "TYPECONFIG_LIST_EXCLUDED_SLUGS",
    "TYPECONFIG_SORT_ORDER_BY_SLUG",
    "TYPECONFIG_SPECS",
    "TYPECONFIG_SPEC_BY_SLUG",
    "TYPECONFIG_UI_SPECS",
    "content_type_ids_for_cot_slugs",
    "default_sort_order_for_slug",
)

TYPECONFIG_LIST_EXCLUDED_SLUGS: frozenset[str] = frozenset({"nsm_object_link"})

TYPECONFIG_SORT_ORDER_BY_SLUG = {
    "nsm_zone": 10,
    "nsm_label": 11,
    "nsm_address": 12,
    "nsm_address_group": 13,
    "nsm_service": 20,
    "nsm_service_group": 21,
    "nsm_app_network": 22,
    "nsm_action": 30,
    "nsm_app_business": 40,
    "nsm_object_link": 50,
}


def default_sort_order_for_slug(slug: str) -> int:
    return TYPECONFIG_SORT_ORDER_BY_SLUG.get(slug, 0)


def content_type_ids_for_cot_slugs(slugs) -> list[int]:
    """Resolve COT slugs to Django ContentType PKs (skips missing types)."""
    try:
        from django.contrib.contenttypes.models import ContentType
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return []

    ids: list[int] = []
    for slug in slugs:
        try:
            cot = CustomObjectType.objects.get(slug=slug)
            ct = ContentType.objects.get_for_model(cot.get_model())
            ids.append(ct.pk)
        except Exception:
            continue
    return ids

REQUIRED_COT_SLUGS = [
    "nsm_action",
    "nsm_service",
    "nsm_service_group",
    "nsm_address",
    "nsm_address_group",
    "nsm_label",
    "nsm_zone",
    "nsm_app_business",
    "nsm_app_network",
    "nsm_object_link",
]

from netbox_nsm.rulebooks.templates import RULEBOOK_TEMPLATE_SLUGS  # noqa: E402

def _typeconfig_spec(
    slug: str,
    label: str,
    *,
    display_template: str,
):
    return {
        "slug": slug,
        "label": label,
        "sort_order": default_sort_order_for_slug(slug),
        "display_template": display_template,
    }


TYPECONFIG_SPECS = [
    _typeconfig_spec("nsm_zone", "Zones", display_template="{{ name }}"),
    _typeconfig_spec("nsm_address", "Addresses", display_template="{{ name }}"),
    _typeconfig_spec("nsm_address_group", "Address Groups", display_template="{{ name }}"),
    _typeconfig_spec(
        "nsm_label",
        "Labels",
        display_template="{{ label_type[0] | upper }}:{{ name }}",
    ),
    _typeconfig_spec(
        "nsm_service",
        "Services",
        display_template="{{ name }} ({{ protocol }}/{{ port }})",
    ),
    _typeconfig_spec("nsm_service_group", "Service Groups", display_template="{{ name }}"),
    _typeconfig_spec("nsm_action", "Action", display_template="{{ name | upper }}"),
    _typeconfig_spec("nsm_app_business", "Business Apps", display_template="{{ name }}"),
    _typeconfig_spec("nsm_app_network", "Network Apps", display_template="{{ name }}"),
    _typeconfig_spec("nsm_object_link", "Object Links", display_template="{{ name }}"),
]

TYPECONFIG_SPEC_BY_SLUG = {spec["slug"]: spec for spec in TYPECONFIG_SPECS}
TYPECONFIG_UI_SPECS = list(TYPECONFIG_SPECS)
