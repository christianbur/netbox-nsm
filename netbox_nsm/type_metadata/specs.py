"""Structural COT slug lists — instance metadata lives in bundle JSON / COT comments."""

__all__ = (
    "REQUIRED_COT_SLUGS",
    "RULEBOOK_TEMPLATE_SLUGS",
    "TYPECONFIG_LIST_EXCLUDED_SLUGS",
    "content_type_ids_for_cot_slugs",
)

TYPECONFIG_LIST_EXCLUDED_SLUGS: frozenset[str] = frozenset({"nsm_object_link"})


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
    "nsm_address_custom",
    "nsm_address_group",
    "nsm_label",
    "nsm_zone",
    "nsm_app_business",
    "nsm_app_network",
    "nsm_object_link",
]

from netbox_nsm.rulebooks.templates import RULEBOOK_TEMPLATE_SLUGS  # noqa: E402
