"""Django system checks for netbox-nsm deployment constraints."""

from django.conf import settings
from django.core.checks import Warning, register

# Plugins that may follow netbox_nsm in ``PLUGINS`` (branching is always last).
_NSM_TRAILING_ALLOWLIST = frozenset({"netbox_branching"})


@register()
def check_nsm_plugin_load_order(app_configs, **kwargs):
    """Warn when plugins listed after netbox_nsm may miss feature tab URLs.

    NetBox builds each plugin's ``get_model_urls()`` snapshot when the root
    URLconf is first loaded. That must happen only after every plugin's
    ``PluginConfig.ready()`` has run ``register_models()`` (contacts, journal,
    changelog). Do not call ``reverse()`` from netbox_nsm ``ready()``; keep
    netbox_nsm last in ``PLUGINS`` except for netbox_branching.
    """
    plugins = list(getattr(settings, "PLUGINS", None) or [])
    if "netbox_nsm" not in plugins:
        return []

    nsm_index = plugins.index("netbox_nsm")
    trailing = [
        name
        for name in plugins[nsm_index + 1 :]
        if name not in _NSM_TRAILING_ALLOWLIST
    ]
    if not trailing:
        return []

    return [
        Warning(
            "netbox_nsm must be listed after other plugins (except netbox_branching). "
            f"Plugins after netbox_nsm: {', '.join(trailing)}. "
            "Their detail pages may miss Contacts/Journal/Changelog tabs.",
            hint="Move netbox_nsm to the last slot before netbox_branching in PLUGINS, "
            "then restart all NetBox workers.",
            id="netbox_nsm.W001",
        )
    ]
