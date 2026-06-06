"""Integration tests for the NSM setup wizard page."""

from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse

from netbox_nsm.models import NsmUiSettings
from utilities.testing import TestCase

_SETUP_PATCHES = {
    "netbox_nsm.views.setup.custom_objects.custom_objects_plugin_loaded": True,
    "netbox_nsm.views.setup.custom_objects.custom_objects_db_ready": True,
    "netbox_nsm.views.setup.custom_objects.get_cot_status": {},
    "netbox_nsm.views.setup.custom_objects.all_cots_ok": True,
    "netbox_nsm.views.setup.custom_objects.empty_cot_status": {},
    "netbox_nsm.views.setup.typeconfig.get_typeconfig_status": {},
    "netbox_nsm.views.setup.typeconfig.empty_typeconfig_status": {},
    "netbox_nsm.views.setup.typeconfig.all_typeconfigs_ok": True,
    "netbox_nsm.branching_support.supports_branching": False,
}


def _apply_setup_patches(test_method):
    for target, value in _SETUP_PATCHES.items():
        if callable(value):
            test_method = patch(target, side_effect=value)(test_method)
        else:
            test_method = patch(target, return_value=value)(test_method)
    return test_method


@override_settings(
    PLUGINS_CONFIG={
        "netbox_nsm": {
            "setup_menu": True,
            "setup_allow_destructive_actions": True,
        }
    }
)
class SetupIntegrationTests(TestCase):
    @_apply_setup_patches
    def test_setup_page_renders(self):
        self.add_permissions("netbox_nsm.view_typeconfig")
        url = reverse("plugins:netbox_nsm:setup")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertContains(response, "setup")

    @_apply_setup_patches
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


@override_settings(
    PLUGINS_CONFIG={
        "netbox_nsm": {
            "setup_menu": False,
        }
    }
)
class SetupHiddenTests(TestCase):
    def test_setup_hidden_when_disabled(self):
        url = reverse("plugins:netbox_nsm:setup")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
