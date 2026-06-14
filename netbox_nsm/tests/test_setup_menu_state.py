"""Setup menu visibility via PLUGINS_CONFIG only."""

from django.test import override_settings

from netbox_nsm.core.setup_flags import setup_menu_enabled
from utilities.testing import TestCase


class SetupMenuStateTests(TestCase):
    @override_settings(PLUGINS_CONFIG={"netbox_nsm": {"setup_menu": True}})
    def test_setup_menu_enabled_by_default_config(self):
        self.assertTrue(setup_menu_enabled())

    @override_settings(PLUGINS_CONFIG={"netbox_nsm": {"setup_menu": False}})
    def test_setup_menu_disabled_via_config(self):
        self.assertFalse(setup_menu_enabled())
