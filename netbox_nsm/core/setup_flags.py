"""Feature flags for the NSM Setup page."""

from netbox.plugins import get_plugin_config

__all__ = (
    "setup_menu_enabled",
    "setup_allow_destructive_actions",
    "sync_setup_menu_config_state",
)


def _setup_menu_config_enabled() -> bool:
    return bool(
        get_plugin_config(
            "netbox_nsm",
            "setup_menu",
            True,
        )
    )


def sync_setup_menu_config_state() -> None:
    """
    Persist PLUGINS_CONFIG ``setup_menu`` transitions.

    When an admin sets ``setup_menu`` back to ``True`` after it was ``False``,
    clear a UI dismiss so the menu reappears.
    """
    from netbox_nsm.models.setup_settings import NsmUiSettings

    current = _setup_menu_config_enabled()
    try:
        solo = NsmUiSettings.get_solo()
    except Exception:
        return

    updates: list[str] = []
    if current and not solo.setup_menu_config_enabled and solo.setup_menu_dismissed:
        solo.setup_menu_dismissed = False
        updates.append("setup_menu_dismissed")
    if current != solo.setup_menu_config_enabled:
        solo.setup_menu_config_enabled = current
        updates.append("setup_menu_config_enabled")
    if updates:
        solo.save(update_fields=updates)


def setup_menu_enabled() -> bool:
    """When True, show Setup in the menu and allow /setup/ URLs."""
    sync_setup_menu_config_state()
    if not _setup_menu_config_enabled():
        return False
    try:
        from netbox_nsm.models.setup_settings import NsmUiSettings

        return not NsmUiSettings.get_solo().setup_menu_dismissed
    except Exception:
        return True


def setup_allow_destructive_actions() -> bool:
    """When False, hide sync/demo buttons and reject related POSTs."""
    return bool(
        get_plugin_config(
            "netbox_nsm",
            "setup_allow_destructive_actions",
            True,
        )
    )
