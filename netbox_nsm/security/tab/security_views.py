"""Security tab view factory and custom-object host view."""

from __future__ import annotations

from django.apps import apps
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.generic import View

from netbox_nsm.core.plugin_labels import get_nsm_panel_label
from netbox_nsm.security.tab.badge import count_security_tab_badge
from netbox_nsm.security.tab.context import build_security_tab_context
from netbox_nsm.security.tab.eligibility import is_security_tab_eligible
from utilities.views import ConditionalLoginRequiredMixin, ViewTab, get_default_template, register_model_view

__all__ = (
    "SECURITY_TAB_PATH",
    "SECURITY_TAB_WEIGHT",
    "SECURITY_VIEW_TAB",
    "make_co_security_view",
    "make_host_security_view",
    "register_security_tab_on_model",
)

SECURITY_TAB_PATH = "security"
SECURITY_TAB_WEIGHT = 1500
SECURITY_VIEW_TAB = ViewTab(
    label=get_nsm_panel_label(),
    badge=count_security_tab_badge,
    weight=SECURITY_TAB_WEIGHT,
    visible=is_security_tab_eligible,
)
_CO_BASE_TEMPLATE = "netbox_custom_objects/customobject.html"
# NSM-scoped custom objects render their detail page (and Journal/Changelog tabs,
# see ``NsmCustomObjectJournalView``) with the NSM template whose tabs block
# includes registry-driven Security via ``nsm_plugin_extra_tabs``. The Security tab
# view must extend the same base so the tab stays visible/active.
_NSM_CO_BASE_TEMPLATE = "netbox_nsm/customobject.html"


def _get_base_template(instance):
    if instance._meta.app_label == "netbox_custom_objects":
        from netbox_nsm.objects.cot_routes import is_nsm_object_menu_slug

        slug = getattr(getattr(instance, "custom_object_type", None), "slug", None)
        if is_nsm_object_menu_slug(slug):
            return _NSM_CO_BASE_TEMPLATE
        return _CO_BASE_TEMPLATE
    return get_default_template(instance)


def _render_security_tab(request, instance, tab):
    if hasattr(instance._meta.model, "objects") and hasattr(
        instance._meta.model.objects, "restrict"
    ):
        qs = instance._meta.model.objects.restrict(request.user, "view")
        instance = get_object_or_404(qs, pk=instance.pk)

    context = build_security_tab_context(instance, request)
    context.update(
        {
            "object": instance,
            "tab": tab,
            "base_template": _get_base_template(instance),
            "nsm_security_tab_mode": True,
            "nsm_panel_label": get_nsm_panel_label(),
        }
    )
    return render(request, "netbox_nsm/security_tab.html", context)


_SECURITY_TAB_REGISTRY_VIEW = None


def _get_security_tab_registry_view():
    """Shared registry view for tab metadata; page is served by ``host_security``."""
    global _SECURITY_TAB_REGISTRY_VIEW
    if _SECURITY_TAB_REGISTRY_VIEW is not None:
        return _SECURITY_TAB_REGISTRY_VIEW

    class SecurityTabRegistryView(ConditionalLoginRequiredMixin, View):
        tab = SECURITY_VIEW_TAB

        def get(self, request, pk, **kwargs):
            raise Http404

    SecurityTabRegistryView.__name__ = "SecurityTabRegistryView"
    SecurityTabRegistryView.__qualname__ = "SecurityTabRegistryView"
    _SECURITY_TAB_REGISTRY_VIEW = SecurityTabRegistryView
    return _SECURITY_TAB_REGISTRY_VIEW


def make_host_security_view():
    """
    Generic Security tab view for built-in and plugin host models.

    Resolves the target model from ``app_label`` / ``model_name`` at request time
    so the tab works regardless of plugin load order or per-model URL snapshots.
    """

    class _HostSecurityTabView(ConditionalLoginRequiredMixin, View):
        tab = SECURITY_VIEW_TAB

        def get(self, request, app_label, model_name, pk, **kwargs):
            try:
                model_class = apps.get_model(app_label, model_name)
            except LookupError:
                raise Http404 from None
            if model_class is None:
                raise Http404
            qs = model_class.objects.all()
            if hasattr(qs, "restrict"):
                qs = qs.restrict(request.user, "view")
            instance = get_object_or_404(qs, pk=pk)
            return _render_security_tab(request, instance, self.tab)

    return _HostSecurityTabView


def make_co_security_view():
    """
    Generic Security tab view for custom-object host pages.

    Resolves the CustomObjectType from the URL slug at request time so the tab
    works for any COT, including ones created after startup.
    """

    class _COSecurityTabView(ConditionalLoginRequiredMixin, View):
        tab = ViewTab(
            label=get_nsm_panel_label(),
            badge=count_security_tab_badge,
            weight=SECURITY_TAB_WEIGHT,
            visible=is_security_tab_eligible,
        )

        def get(self, request, custom_object_type, pk, **kwargs):
            from netbox_custom_objects.models import CustomObjectType

            cot = get_object_or_404(CustomObjectType, slug=custom_object_type)
            actual_model = cot.get_model()
            qs = actual_model.objects.all()
            if hasattr(qs, "restrict"):
                qs = qs.restrict(request.user, "view")
            instance = get_object_or_404(qs, pk=pk)
            return _render_security_tab(request, instance, self.tab)

    return _COSecurityTabView


def register_security_tab_on_model(model_class) -> bool:
    """Register the Security tab on ``model_class`` if not already present."""
    from netbox.registry import registry

    app_label = model_class._meta.app_label
    model_name = model_class._meta.model_name
    existing = registry["views"].get(app_label, {}).get(model_name, [])
    if any(entry["name"] == SECURITY_TAB_PATH for entry in existing):
        return False
    register_model_view(
        model_class,
        name=SECURITY_TAB_PATH,
        path=SECURITY_TAB_PATH,
    )(_get_security_tab_registry_view())
    return True
