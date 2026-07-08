"""Plugin sidebar menu registration."""

from django.test import TestCase

from django.utils.translation import gettext as _

from netbox.plugins import PluginMenu, PluginMenuItem
from netbox.registry import registry

from netbox_nsm import navigation
from netbox_nsm.core.plugin_labels import get_nsm_menu_label


class NavigationMenuTests(TestCase):
    def test_top_level_menu_registered(self):
        menus = [
            menu
            for menu in registry["plugins"]["menus"]
            if isinstance(menu, navigation.DynamicPluginMenu)
        ]
        self.assertEqual(len(menus), 1)

    def test_dynamic_menu_is_plugin_menu(self):
        self.assertTrue(
            any(
                isinstance(menu, PluginMenu)
                for menu in registry["plugins"]["menus"]
                if isinstance(menu, navigation.DynamicPluginMenu)
            )
        )

    def test_menu_label_not_empty(self):
        label = str(get_nsm_menu_label()).strip()
        self.assertTrue(label)

    def test_menu_groups_have_items(self):
        menu = next(
            menu
            for menu in registry["plugins"]["menus"]
            if isinstance(menu, navigation.DynamicPluginMenu)
        )
        groups = navigation.build_menu_groups()
        self.assertGreaterEqual(len(groups), 3)
        for _label, items in groups:
            self.assertGreater(len(items), 0)
            for item in items:
                self.assertIsInstance(item, PluginMenuItem)

        rendered_groups = menu.groups
        self.assertEqual(len(rendered_groups), len(groups))
        self.assertGreater(len(rendered_groups[0].items), 0)

    def test_configuration_group_always_has_object_config(self):
        config_group = navigation._build_configuration_menu()[0]
        links = {item.link for item in config_group[1]}
        self.assertIn("plugins:netbox_nsm:typemetadata_list", links)
        self.assertIn("plugins:netbox_nsm:object_link_config", links)
        self.assertNotIn("plugins:netbox_nsm:object_sync", links)

    def test_objects_group_not_in_menu(self):
        groups = navigation.build_menu_groups()
        object_groups = [group for group in groups if str(group[0]) == str(_("Objects"))]
        self.assertEqual(object_groups, [])
