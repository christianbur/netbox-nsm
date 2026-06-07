"""Setup menu dismiss and config restore."""

from django.test import override_settings

from netbox_nsm.models import NsmUiSettings
from netbox_nsm.setup_flags import setup_menu_enabled, sync_setup_menu_config_state
from utilities.testing import TestCase


class SetupMenuStateTests(TestCase):
    @override_settings(
        PLUGINS_CONFIG={
            "netbox_nsm": {"setup_menu": True},
            "netbox_branching": {},
        }
    )
    def test_dismissed_hides_menu_while_config_true(self):
        solo = NsmUiSettings.get_solo()
        solo.setup_menu_dismissed = True
        solo.setup_menu_config_enabled = True
        solo.save(update_fields=["setup_menu_dismissed", "setup_menu_config_enabled"])
        self.assertFalse(setup_menu_enabled())

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_nsm": {"setup_menu": False},
            "netbox_branching": {},
        }
    )
    def test_config_false_hides_menu(self):
        solo = NsmUiSettings.get_solo()
        solo.setup_menu_dismissed = False
        solo.setup_menu_config_enabled = True
        solo.save(update_fields=["setup_menu_dismissed", "setup_menu_config_enabled"])
        self.assertFalse(setup_menu_enabled())

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_nsm": {"setup_menu": True},
            "netbox_branching": {},
        }
    )
    def test_config_true_after_false_clears_dismiss(self):
        solo = NsmUiSettings.get_solo()
        solo.setup_menu_dismissed = True
        solo.setup_menu_config_enabled = False
        solo.save(update_fields=["setup_menu_dismissed", "setup_menu_config_enabled"])
        sync_setup_menu_config_state()
        solo.refresh_from_db()
        self.assertFalse(solo.setup_menu_dismissed)
        self.assertTrue(solo.setup_menu_config_enabled)
        self.assertTrue(setup_menu_enabled())
