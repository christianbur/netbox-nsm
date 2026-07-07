"""Generic host-model Security tab URL routing (Approach B)."""

from __future__ import annotations

from django.urls import reverse

from netbox_nsm.security.tab.security_views import SECURITY_TAB_PATH

HOST_SECURITY_URL_NAME = "host_security"

__all__ = (
    "HOST_SECURITY_URL_NAME",
    "apply_host_security_url_patches",
    "host_security_reverse",
    "host_security_viewname",
)


def host_security_viewname() -> str:
    return f"plugins:netbox_nsm:{HOST_SECURITY_URL_NAME}"


def host_security_reverse(app_label: str, model_name: str, *, pk: int) -> str:
    return reverse(
        host_security_viewname(),
        kwargs={"app_label": app_label, "model_name": model_name, "pk": pk},
    )


def apply_host_security_url_patches() -> None:
    """Route built-in/plugin Security tab links through the generic host URL."""
    import utilities.views as utilities_views

    if getattr(utilities_views.get_action_url, "_nsm_host_security_patch", False):
        return

    original_get_action_url = utilities_views.get_action_url

    def patched_get_action_url(model, action=None, rest_api=False, kwargs=None):
        if action == SECURITY_TAB_PATH and not rest_api:
            if model._meta.app_label == "netbox_custom_objects":
                if hasattr(model, "_get_action_url"):
                    return model._get_action_url(action, rest_api, kwargs)
            pk = (kwargs or {}).get("pk")
            if pk is None and getattr(model, "pk", None):
                pk = model.pk
            if pk is not None:
                return host_security_reverse(
                    model._meta.app_label,
                    model._meta.model_name,
                    pk=pk,
                )
        return original_get_action_url(
            model, action=action, rest_api=rest_api, kwargs=kwargs
        )

    patched_get_action_url._nsm_host_security_patch = True
    utilities_views.get_action_url = patched_get_action_url
