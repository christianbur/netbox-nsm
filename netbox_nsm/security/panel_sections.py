"""Static panel/field slug definitions (replaces the removed SecurityArea model)."""

from django.utils.translation import gettext_lazy as _

PANEL_SECTIONS = (
    {"slug": "source", "name": _("Source"), "sort_order": 10},
    {"slug": "destination", "name": _("Destination"), "sort_order": 20},
    {"slug": "services", "name": _("Services"), "sort_order": 30},
    {"slug": "action", "name": _("Action"), "sort_order": 40},
    {"slug": "info", "name": _("Info"), "sort_order": 50},
)


def get_panel_sections():
    return PANEL_SECTIONS


def get_default_panel_slug():
    return PANEL_SECTIONS[0]["slug"]
