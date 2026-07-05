"""Feature flags for the Bundles page and related bundle actions."""

from netbox.plugins import get_plugin_config

__all__ = (
    "setup_menu_enabled",
    "setup_allow_destructive_actions",
)


def setup_menu_enabled() -> bool:
    """When True, show Bundles in the menu and allow /bundles/ URLs."""
    from django.conf import settings

    nsm_cfg = settings.PLUGINS_CONFIG.get("netbox_nsm", {})
    if "bundles_menu" in nsm_cfg:
        return bool(nsm_cfg["bundles_menu"])
    if "setup_menu" in nsm_cfg:
        return bool(nsm_cfg["setup_menu"])
    return bool(get_plugin_config("netbox_nsm", "bundles_menu", True))


def setup_allow_destructive_actions() -> bool:
    """When False, hide sync/demo buttons and reject related POSTs."""
    return bool(
        get_plugin_config(
            "netbox_nsm",
            "setup_allow_destructive_actions",
            True,
        )
    )
