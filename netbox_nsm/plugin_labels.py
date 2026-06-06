"""Menu and panel titles: Setup DB → PLUGINS_CONFIG → default."""

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from netbox_nsm.models.setup_settings import DEFAULT_MENU_LABEL, DEFAULT_PANEL_LABEL

__all__ = ("get_nsm_menu_label", "get_nsm_panel_label")


def _plugin_config() -> dict:
    return settings.PLUGINS_CONFIG.get("netbox_nsm", {})


def _db_settings():
    try:
        from netbox_nsm.models import NsmUiSettings

        return NsmUiSettings.get_solo()
    except Exception:
        return None


def get_nsm_menu_label():
    """Top-level plugin menu label."""
    db = _db_settings()
    if db and db.menu_label:
        return db.menu_label
    custom = _plugin_config().get("menu_label")
    if custom:
        return str(custom)
    return _(DEFAULT_MENU_LABEL)


def get_nsm_panel_label():
    """Security panel card title on object detail pages."""
    db = _db_settings()
    if db:
        return db.resolved_panel_label()
    custom = _plugin_config().get("panel_label")
    if custom:
        return str(custom)
    return _(DEFAULT_PANEL_LABEL)
