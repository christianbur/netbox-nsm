"""Integration tests for the NSM setup wizard page."""

from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse

from netbox_nsm.models import NsmUiSettings
from netbox_nsm.views.setup import ui_settings
from utilities.testing import TestCase

_SETUP_PLUGINS_CONFIG = {
    "netbox_nsm": {
        "setup_menu": True,
        "setup_allow_destructive_actions": True,
    },
    "netbox_branching": {},
}


@override_settings(PLUGINS_CONFIG=_SETUP_PLUGINS_CONFIG)
class SetupIntegrationTests(TestCase):
    @patch(
        "netbox_nsm.views.setup.view.SetupView._build_context",
        return_value={
            "custom_objects_plugin_loaded": True,
            "custom_objects_db_ready": True,
            "cot_status": {},
            "tc_status": {},
            "all_cots_ok": True,
            "all_tcs_ok": True,
            "can_import_cots": False,
            "can_create_typeconfigs": False,
            "can_run_demo": False,
            "setup_allow_destructive_actions": True,
            "ui_settings": ui_settings.get_ui_settings(),
        },
    )
    def test_setup_page_renders(self, _build_context):
        self.add_permissions("netbox_nsm.view_typeconfig")
        url = reverse("plugins:netbox_nsm:setup")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertContains(response, "setup")

    def test_save_ui_settings_updates_db(self):
        self.add_permissions("netbox_nsm.view_typeconfig")
        url = reverse("plugins:netbox_nsm:setup")
        response = self.client.post(
            url,
            {
                "action": "save_ui_settings",
                "menu_label": "Test Menu",
                "panel_label": "Test Panel",
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        settings_obj = NsmUiSettings.get_solo()
        self.assertEqual(settings_obj.menu_label, "Test Menu")
        self.assertEqual(settings_obj.panel_label, "Test Panel")

    def test_hide_setup_menu_dismisses_entry(self):
        self.add_permissions("netbox_nsm.view_typeconfig")
        url = reverse("plugins:netbox_nsm:setup")
        response = self.client.post(url, {"action": "hide_setup_menu"})
        self.assertEqual(response.status_code, 302, response.content)
        settings_obj = NsmUiSettings.get_solo()
        self.assertTrue(settings_obj.setup_menu_dismissed)
        from netbox_nsm.core.setup_flags import setup_menu_enabled

        self.assertFalse(setup_menu_enabled())


class SetupHiddenTests(TestCase):
    @patch("netbox_nsm.views.setup.view.setup_menu_enabled", return_value=False)
    def test_setup_hidden_when_disabled(self, _menu_enabled):
        url = reverse("plugins:netbox_nsm:setup")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
