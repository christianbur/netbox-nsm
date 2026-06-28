"""Template tags for the NSM Security detail tab."""

from django import template
from django.urls.exceptions import NoReverseMatch
from django.utils.module_loading import import_string

from netbox.registry import registry
from utilities.views import get_action_url

register = template.Library()

# Rendered explicitly on NSM ``customobject.html`` (see ``nsm_security_tab_link``).
_HARDCODED_TAB_NAMES = frozenset({"journal", "changelog", "custom_objects", "security"})


@register.inclusion_tag("tabs/model_view_tabs.html", takes_context=True)
def nsm_plugin_extra_tabs(context, instance):
    """
    Render registered model-view tabs, excluding tabs already rendered manually
    on NSM custom-object detail pages.
    """
    app_label = instance._meta.app_label
    model_name = instance._meta.model_name
    user = context["request"].user
    tabs = []

    try:
        views = registry["views"][app_label][model_name]
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
                    url = get_action_url(
                        instance,
                        action=config["name"],
                        kwargs={"pk": instance.pk},
                    )
                except NoReverseMatch:
                    continue
                tabs.append(
                    {
                        "name": config["name"],
                        "url": url,
                        "label": attrs["label"],
                        "badge": attrs["badge"],
                        "weight": attrs["weight"],
                        "is_active": context.get("tab") == tab,
                    }
                )

    tabs = sorted(tabs, key=lambda row: row["weight"])
    return {"tabs": tabs}


@register.inclusion_tag(
    "netbox_nsm/inc/security_tab_link.html",
    takes_context=True,
)
def nsm_security_tab_link(context, instance):
    """
    Render the Security tab nav-link on custom-object detail pages.

    Badge is computed live from the DB; the tab is always shown (like the
    legacy right-hand Security panel on every object page).
    """
    from netbox_nsm.core.plugin_labels import get_nsm_panel_label
    from netbox_nsm.tabs.badge import count_security_tab_badge

    try:
        url = get_action_url(
            instance,
            action="security",
            kwargs={"pk": instance.pk},
        )
    except NoReverseMatch:
        return {"tab": None}

    request = context.get("request")
    is_active = request is not None and request.path == url
    badge = count_security_tab_badge(instance)

    return {
        "tab": {
            "url": url,
            "label": get_nsm_panel_label(),
            "badge": badge or None,
            "is_active": is_active,
        }
    }
