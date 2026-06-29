"""Template tags for registry-driven tabs on NSM custom-object detail pages."""

from django import template
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from django.utils.module_loading import import_string

from netbox.registry import registry
from utilities.views import get_action_url

register = template.Library()

# journal/changelog/custom_objects are rendered as hardcoded <li>s on NSM
# ``customobject.html`` (NSM-scoped journal/changelog URLs). Security is rendered
# via this tag from ``register_model_view`` + injected CO/NSM security URLs.
_HARDCODED_TAB_NAMES = frozenset({"journal", "changelog", "custom_objects"})


def _registry_model_name(instance) -> str:
    """
    Registry views for custom objects are keyed on ``CustomObject`` (``customobject``),
    not on each dynamic table model (e.g. ``table7model``).
    """
    if instance._meta.app_label == "netbox_custom_objects":
        return "customobject"
    return instance._meta.model_name


def _get_tab_action_url(instance, action, kwargs=None) -> str:
    """
    Resolve tab URLs for custom-object instances.

    ``utilities.views.get_action_url`` delegates to the dynamic model's
    ``_get_action_url``, which always targets netbox-custom-objects routes.
    Use the patched ``get_viewname`` helper instead so menu=objects COTs resolve
    to ``plugins:netbox_nsm:nsm_object_*`` URLs.
    """
    kwargs = dict(kwargs or {})
    if kwargs.get("pk") is None and getattr(instance, "pk", None) is not None:
        kwargs["pk"] = instance.pk

    if instance._meta.app_label == "netbox_custom_objects":
        from netbox_custom_objects.utilities import get_viewname

        slug = getattr(getattr(instance, "custom_object_type", None), "slug", None)
        if slug is not None:
            kwargs.setdefault("custom_object_type", slug)
        return reverse(get_viewname(instance, action=action), kwargs=kwargs)

    return get_action_url(instance, action=action, kwargs=kwargs)


@register.inclusion_tag("tabs/model_view_tabs.html", takes_context=True)
def nsm_plugin_extra_tabs(context, instance):
    """
    Render registered model-view tabs, excluding tabs already rendered manually
    on NSM custom-object detail pages.
    """
    app_label = instance._meta.app_label
    registry_model_name = _registry_model_name(instance)
    user = context["request"].user
    request = context.get("request")
    tabs = []

    try:
        views = registry["views"][app_label][registry_model_name]
    except KeyError:
        views = []

    for config in views:
        if config["name"] in _HARDCODED_TAB_NAMES:
            continue
        view = (
            import_string(config["view"])
            if type(config["view"]) is str
            else config["view"]
        )
        if tab := getattr(view, "tab", None):
            if tab.permission and not user.has_perm(tab.permission):
                continue
            if attrs := tab.render(instance):
                try:
                    url = _get_tab_action_url(
                        instance,
                        action=config["name"],
                        kwargs={"pk": instance.pk},
                    )
                except NoReverseMatch:
                    continue
                is_active = context.get("tab") == tab
                # Custom-object host pages use injected generic routes; compare the
                # request path to the tab URL (PR 482 ``custom_objects_tab_link`` pattern).
                if app_label == "netbox_custom_objects" and request is not None:
                    is_active = request.path == url
                tabs.append(
                    {
                        "name": config["name"],
                        "url": url,
                        "label": attrs["label"],
                        "badge": attrs["badge"],
                        "weight": attrs["weight"],
                        "is_active": is_active,
                    }
                )

    tabs = sorted(tabs, key=lambda row: row["weight"])
    return {"tabs": tabs}
