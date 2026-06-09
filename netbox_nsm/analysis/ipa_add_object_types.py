"""Search catalog for the IP Analyzer applet "Add object" picker."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _

from netbox_nsm.core.api_urls import get_api_url_for_content_type

__all__ = ("build_ipa_add_object_categories",)

_IPAM_CT_KEYS = (
    ("ipam", "prefix", _("Prefix")),
    ("ipam", "ipaddress", _("IP Address")),
    ("ipam", "iprange", _("IP Range")),
)

_COT_CATEGORIES = (
    ("nsm_address", _("Address")),
    ("nsm_address_group", _("Address Group")),
)


def _search_type_for_content_type(ct, *, name: str) -> dict | None:
    api_url = get_api_url_for_content_type(ct)
    if not api_url:
        return None
    return {"ct_id": ct.pk, "api_url": api_url, "name": str(name)}


def _cot_search_type(slug: str, label) -> dict | None:
    try:
        from netbox_custom_objects.models import CustomObjectType

        cot = CustomObjectType.objects.filter(slug=slug).only("pk", "slug").first()
        if not cot:
            return None
        ct = ContentType.objects.get(
            app_label="netbox_custom_objects",
            model=f"table{cot.pk}model",
        )
        return _search_type_for_content_type(ct, name=label)
    except Exception:
        return None


def build_ipa_add_object_categories() -> list[dict]:
    """Return grouped REST search targets for IPAM and NSM address objects."""
    categories: list[dict] = []

    ipam_types: list[dict] = []
    for app, model, label in _IPAM_CT_KEYS:
        try:
            ct = ContentType.objects.get(app_label=app, model=model)
        except ContentType.DoesNotExist:
            continue
        entry = _search_type_for_content_type(ct, name=label)
        if entry:
            ipam_types.append(entry)
    if ipam_types:
        categories.append(
            {
                "id": "ipam",
                "label": str(_("IPAM")),
                "types": ipam_types,
            }
        )

    for slug, label in _COT_CATEGORIES:
        entry = _cot_search_type(slug, label)
        if entry:
            categories.append(
                {
                    "id": slug,
                    "label": str(label),
                    "types": [entry],
                }
            )

    return categories
