"""Tests for configurable menu/panel labels."""

from django.test import TestCase, override_settings

from netbox_nsm.models import NsmUiSettings
from netbox_nsm.plugin_labels import get_nsm_menu_label, get_nsm_panel_label


class PluginLabelsTest(TestCase):
    @override_settings(PLUGINS_CONFIG={"netbox_nsm": {}})
    def test_defaults_use_security(self):
        self.assertEqual(str(get_nsm_menu_label()), "Security")
        self.assertEqual(str(get_nsm_panel_label()), "Security")

    @override_settings(PLUGINS_CONFIG={"netbox_nsm": {"menu_label": "Netz-Security"}})
    def test_menu_label_custom(self):
        self.assertEqual(get_nsm_menu_label(), "Netz-Security")

    @override_settings(
        PLUGINS_CONFIG={"netbox_nsm": {"menu_label": "Menu", "panel_label": "Panel"}}
    )
    def test_panel_label_independent(self):
        self.assertEqual(get_nsm_panel_label(), "Panel")

    @override_settings(PLUGINS_CONFIG={"netbox_nsm": {"menu_label": "Menu Only"}})
    def test_panel_falls_back_to_menu_label(self):
        self.assertEqual(get_nsm_panel_label(), "Menu Only")

    def test_db_settings_override_config(self):
        NsmUiSettings.objects.create(pk=1, menu_label="From DB", panel_label="Panel DB")
        self.assertEqual(get_nsm_menu_label(), "From DB")
        self.assertEqual(get_nsm_panel_label(), "Panel DB")
