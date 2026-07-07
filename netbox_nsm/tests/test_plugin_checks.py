"""Tests for netbox-nsm Django system checks."""

from django.core.checks import Warning
from django.test import SimpleTestCase, override_settings

from netbox_nsm.checks import check_nsm_plugin_load_order


class NsmPluginLoadOrderCheckTests(SimpleTestCase):
    @override_settings(
        PLUGINS=[
            "netbox_load_balancing",
            "netbox_nsm",
            "netbox_branching",
        ]
    )
    def test_no_warning_when_nsm_is_last_before_branching(self):
        self.assertEqual(check_nsm_plugin_load_order(None), [])

    @override_settings(
        PLUGINS=[
            "netbox_nsm",
            "netbox_load_balancing",
        ]
    )
    def test_warning_when_plugins_follow_nsm(self):
        messages = check_nsm_plugin_load_order(None)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].id, "netbox_nsm.W001")
        self.assertIsInstance(messages[0], Warning)
        self.assertIn("netbox_load_balancing", messages[0].msg)
