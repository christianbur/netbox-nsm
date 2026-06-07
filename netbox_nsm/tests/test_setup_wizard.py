"""Setup wizard: every template action must map to a handler."""

from django.test import SimpleTestCase

from netbox_nsm.views.setup import custom_objects, demo, typeconfig, ui_settings

# Actions emitted by templates under netbox_nsm/templates/netbox_nsm/inc/setup_*.html
WIZARD_ACTIONS = {
    "save_ui_settings": ui_settings.handles_action,
    "import_all_types": custom_objects.handles_action,
    "create_all_typeconfigs": typeconfig.handles_action,
    "create_demo_starter": demo.handles_action,
}


class SetupWizardActionTests(SimpleTestCase):
    def test_all_template_actions_have_handlers(self):
        for action, handles in WIZARD_ACTIONS.items():
            with self.subTest(action=action):
                self.assertTrue(handles(action))

    def test_demo_actions_complete(self):
        self.assertEqual(
            demo.DEMO_ACTIONS,
            {
                "create_demo_starter",
                "create_demo_enterprise",
                "create_demo_addresses_scale",
                "create_demo_scale",
            },
        )
