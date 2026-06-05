"""Resolve REST API list URLs for ContentTypes (custom objects, plugins, core apps)."""

from django.contrib.contenttypes.models import ContentType
from django.urls import NoReverseMatch, reverse

__all__ = ("get_api_url_for_content_type",)


def get_api_url_for_content_type(ct: ContentType) -> str | None:
    import re

    app = ct.app_label
    model = ct.model

    if app == "netbox_custom_objects":
        m = re.match(r"^table(\d+)model$", model)
        if m:
            try:
                from netbox_custom_objects.models import CustomObjectType

                cot = CustomObjectType.objects.get(pk=int(m.group(1)))
                return f"/api/plugins/custom-objects/{cot.slug}/"
            except Exception:
                pass
        return None

    try:
        return reverse(f"{app}-api:{model}-list")
    except NoReverseMatch:
        pass
    try:
        return reverse(f"plugins-api:{app}-api:{model}-list")
    except NoReverseMatch:
        pass
    return None
