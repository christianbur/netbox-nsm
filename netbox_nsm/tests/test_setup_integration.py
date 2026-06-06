"""Integration tests for the NSM setup wizard page."""

from contextlib import ExitStack
from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse

from netbox_nsm.models import NsmUiSettings
from utilities.testing import TestCase


def _setup_context_patches():
    stack = ExitStack()
    stack.enter_context(
        patch(
            "netbox_nsm.views.setup.view.custom_objects.custom_objects_plugin_loaded",
            return_value=True,
        )
    )
    stack.enter_context(
        patch(
            "netbox_nsm.views.setup.view.custom_objects.custom_objects_db_ready",
            return_value=True,
        )
    )
    stack.enter_context(
        patch(
            "netbox_nsm.views.setup.view.custom_objects.get_cot_status",
            return_value={},
        )
    )
    stack.enter_context(
        patch(
            "netbox_nsm.views.setup.view.custom_objects.all_cots_ok",
            return_value=True,
        )
    )
    stack.enter_context(
        patch(
            "netbox_nsm.views.setup.view.custom_objects.empty_cot_status",
            return_value={},
        )
    )
    stack.enter_context(
        patch(
            "netbox_nsm.views.setup.view.typeconfig.get_typeconfig_status",
            return_value={},
        )
    )
    stack.enter_context(
        patch(
            "netbox_nsm.views.setup.view.typeconfig.empty_typeconfig_status",
            return_value={},
        )
    )
    stack.enter_context(
        patch(
            "netbox_nsm.views.setup.view.typeconfig.all_typeconfigs_ok",
            return_value=True,
        )
    )
    return stack


@override_settings(
    PLUGINS_CONFIG={
        "netbox_nsm": {
            "setup_menu": True,
            "setup_allow_destructive_actions": True,
        }
    }
)
class SetupIntegrationTests(TestCase):
    def test_setup_page_renders(self):
        self.add_permissions("netbox_nsm.view_typeconfig")
        url = reverse("plugins:netbox_nsm:setup")
        with _setup_context_patches():
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertContains(response, "setup")

    def test_save_ui_settings_updates_db(self):
        self.add_permissions("netbox_nsm.view_typeconfig")
        url = reverse("plugins:netbox_nsm:setup")
        with _setup_context_patches():
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
    def test_setup_hidden_when_disabled(self):
        url = reverse("plugins:netbox_nsm:setup")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
