"""Plugin menu and panel labels from PLUGINS_CONFIG."""

from django.test import override_settings

from netbox_nsm.core.plugin_labels import get_nsm_menu_label, get_nsm_panel_label
from utilities.testing import TestCase


class PluginLabelsTests(TestCase):
    @override_settings(PLUGINS_CONFIG={"netbox_nsm": {}})
    def test_defaults_when_config_empty(self):
        self.assertEqual(str(get_nsm_menu_label()), "Security")
        self.assertEqual(str(get_nsm_panel_label()), "Security")

    @override_settings(
        PLUGINS_CONFIG={"netbox_nsm": {"menu_label": "NetSec", "panel_label": "Panel X"}}
    )
    def test_custom_labels_from_plugins_config(self):
        self.assertEqual(str(get_nsm_menu_label()), "NetSec")
        self.assertEqual(str(get_nsm_panel_label()), "Panel X")

    @override_settings(PLUGINS_CONFIG={"netbox_nsm": {"menu_label": "Only Menu"}})
    def test_panel_falls_back_to_menu_label(self):
        self.assertEqual(str(get_nsm_panel_label()), "Only Menu")
