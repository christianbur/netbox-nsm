"""Register the Security tab on all public NetBox object types."""

from __future__ import annotations

import logging

from django.urls import clear_url_caches, path as url_path

from utilities.views import register_model_view

from netbox_nsm.security.tab.security_views import (
    SECURITY_TAB_PATH,
    make_co_security_view,
    register_security_tab_on_model,
)

logger = logging.getLogger("netbox_nsm.tabs")

# URL name for custom-object host pages (``CustomObject._get_viewname('security')``).
CO_SECURITY_URL_NAME = f"customobject_{SECURITY_TAB_PATH}"
NSM_OBJECT_SECURITY_URL_NAME = f"nsm_object_{SECURITY_TAB_PATH}"


def _inject_co_security_url():
    """
    Inject a slug-agnostic Security tab URL for custom-object host pages.

    Custom-object detail pages are served by one generic view and never call
    ``get_model_urls()``, so the tab needs a COT-agnostic route injected at
    ready() time.
    """
    try:
        import netbox_custom_objects.urls as co_urls
    except ImportError:
        return

    existing_names = {p.name for p in co_urls.urlpatterns if hasattr(p, "name") and p.name}
    if CO_SECURITY_URL_NAME in existing_names:
        return

    full_path = f"<str:custom_object_type>/<int:pk>/{SECURITY_TAB_PATH}/"
    co_urls.urlpatterns.append(
        url_path(
            full_path,
            make_co_security_view().as_view(),
            name=CO_SECURITY_URL_NAME,
        )
    )
    logger.debug("injected URL pattern '%s'", CO_SECURITY_URL_NAME)


def _inject_nsm_object_security_url():
    """
    Inject Security tab URL for NSM-scoped custom object routes.

    The route is declared statically in ``netbox_nsm.urls`` (alongside journal and
    changelog) because importing that module from ``ready()`` can finish loading
    ``urlpatterns`` after this append, discarding runtime injection. Keep this helper
    as an idempotent fallback for older deployments.
    """
    try:
        import netbox_nsm.urls as nsm_urls
    except ImportError:
        return

    existing_names = {
        p.name for p in nsm_urls.urlpatterns if hasattr(p, "name") and p.name
    }
    if NSM_OBJECT_SECURITY_URL_NAME in existing_names:
        return

    full_path = f"objects/<str:custom_object_type>/<int:pk>/{SECURITY_TAB_PATH}/"
    nsm_urls.urlpatterns.append(
        url_path(
            full_path,
            make_co_security_view().as_view(),
            name=NSM_OBJECT_SECURITY_URL_NAME,
        )
    )
    logger.debug("injected URL pattern '%s'", NSM_OBJECT_SECURITY_URL_NAME)


def _public_host_model_classes():
    """
    Return model classes that should receive a registry-driven Security tab.

    Mirrors netbox-custom-objects ``related_tabs`` host enumeration: every
    public ``ObjectType`` except dynamic custom-object models (those use the
    injected generic URL plus ``nsm_plugin_extra_tabs`` on the detail template).
    """
    from core.models import ObjectType
    from django.db.utils import OperationalError, ProgrammingError

    try:
        object_types = list(
            ObjectType.objects.public().exclude(app_label="netbox_custom_objects")
        )
    except (OperationalError, ProgrammingError):
        logger.warning(
            "database unavailable — Security tab not registered until next start"
        )
        return []

    seen: set[tuple[str, str]] = set()
    result = []
    for ot in object_types:
        try:
            model = ot.model_class()
        except Exception:
            logger.exception(
                "skipping ObjectType pk=%s (%s.%s): error resolving model class",
                ot.pk,
                ot.app_label,
                ot.model,
            )
            continue
        if model is None:
            logger.warning(
                "skipping ObjectType pk=%s (%s.%s): no installed model",
                ot.pk,
                ot.app_label,
                ot.model,
            )
            continue
        key = (model._meta.app_label, model._meta.model_name)
        if key in seen:
            continue
        seen.add(key)
        result.append(model)
    return result


def _register_custom_object_security_tab():
    """
    Register Security on ``CustomObject`` using the generic CO host view.

    The tab nav-link is rendered by ``nsm_plugin_extra_tabs``; the page is
    served by the slug-agnostic route injected in ``_inject_co_security_url``
    / ``_inject_nsm_object_security_url`` (same split as CO PR 482 combined tab).
    """
    try:
        from netbox_custom_objects.models import CustomObject
    except ImportError:
        return

    from netbox.registry import registry

    app_label = CustomObject._meta.app_label
    model_name = CustomObject._meta.model_name
    existing = registry["views"].get(app_label, {}).get(model_name, [])
    if any(entry["name"] == SECURITY_TAB_PATH for entry in existing):
        return

    register_model_view(
        CustomObject,
        name=SECURITY_TAB_PATH,
        path=SECURITY_TAB_PATH,
    )(make_co_security_view())


def register_security_tabs():
    """
    Register the Security tab on all public models and inject CO host URLs.

    Must run synchronously from ``SecurityConfig.ready()`` before the URLconf
    freezes on first resolve.
    """
    try:
        _inject_co_security_url()
        _inject_nsm_object_security_url()
        for model_class in _public_host_model_classes():
            register_security_tab_on_model(model_class)
        _register_custom_object_security_tab()
    finally:
        clear_url_caches()
