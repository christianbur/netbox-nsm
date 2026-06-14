"""Feature flags for the NSM Setup page."""

from netbox.plugins import get_plugin_config

__all__ = (
    "setup_menu_enabled",
    "setup_allow_destructive_actions",
)


def setup_menu_enabled() -> bool:
    """When True, show Setup in the menu and allow /setup/ URLs."""
    return bool(
        get_plugin_config(
            "netbox_nsm",
            "setup_menu",
            True,
        )
    )


def setup_allow_destructive_actions() -> bool:
    """When False, hide sync/demo buttons and reject related POSTs."""
    return bool(
        get_plugin_config(
            "netbox_nsm",
            "setup_allow_destructive_actions",
            True,
        )
    )
