"""Setup: menu and panel label configuration."""

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox_nsm.models import NsmUiSettings
from netbox_nsm.models.setup_settings import DEFAULT_MENU_LABEL, DEFAULT_PANEL_LABEL

__all__ = (
    "get_ui_settings",
    "handles_action",
    "handle_ui_settings_action",
)


def get_ui_settings() -> NsmUiSettings:
    try:
        return NsmUiSettings.get_solo()
    except Exception:
        return NsmUiSettings(
            menu_label=DEFAULT_MENU_LABEL,
            panel_label=DEFAULT_PANEL_LABEL,
        )


def handles_action(action: str) -> bool:
    return action in ("save_ui_settings", "hide_setup_menu")


def handle_ui_settings_action(request, action: str):
    if action == "hide_setup_menu":
        settings_obj = NsmUiSettings.get_solo()
        settings_obj.setup_menu_dismissed = True
        settings_obj.save(update_fields=["setup_menu_dismissed"])
        messages.success(
            request,
            _(
                "Setup has been hidden from the menu. To show it again, set "
                '"setup_menu": true in PLUGINS_CONFIG["netbox_nsm"] after toggling '
                "it to false and restarting NetBox."
            ),
        )
        return redirect(reverse("plugins:netbox_nsm:rulebook_list"))

    if action != "save_ui_settings":
        return redirect(reverse("plugins:netbox_nsm:setup"))

    menu_label = (request.POST.get("menu_label") or "").strip()
    panel_label = (request.POST.get("panel_label") or "").strip()
    if not menu_label:
        messages.error(request, _("Menu label is required."))
        return redirect(reverse("plugins:netbox_nsm:setup"))

    settings_obj = NsmUiSettings.get_solo()
    settings_obj.menu_label = menu_label[:100]
    settings_obj.panel_label = (panel_label or DEFAULT_PANEL_LABEL)[:100]
    settings_obj.save(update_fields=["menu_label", "panel_label"])
    messages.success(request, _("Menu and panel labels saved."))
    return redirect(reverse("plugins:netbox_nsm:setup"))
