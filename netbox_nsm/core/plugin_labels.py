"""Menu and panel titles from PLUGINS_CONFIG only."""

from django.conf import settings
from django.utils.translation import gettext_lazy as _

__all__ = ("DEFAULT_MENU_LABEL", "DEFAULT_PANEL_LABEL", "get_nsm_menu_label", "get_nsm_panel_label")

DEFAULT_MENU_LABEL = "Security"
DEFAULT_PANEL_LABEL = "Security"


def _plugin_config() -> dict:
    return settings.PLUGINS_CONFIG.get("netbox_nsm", {})


def get_nsm_menu_label():
    """Top-level plugin menu label."""
    custom = _plugin_config().get("menu_label")
    if custom:
        return str(custom)
    return _(DEFAULT_MENU_LABEL)


def get_nsm_panel_label():
    """Security panel card title on object detail pages."""
    custom = _plugin_config().get("panel_label")
    if custom:
        return str(custom)
    menu_custom = _plugin_config().get("menu_label")
    if menu_custom:
        return str(menu_custom)
    return _(DEFAULT_PANEL_LABEL)
