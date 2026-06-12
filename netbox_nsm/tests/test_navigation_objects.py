"""Tests for NSM object entries in the Security menu."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox.plugins import PluginMenuItem

from netbox_nsm.navigation_objects import (
    build_nsm_objects_menu_group,
    iter_nsm_object_menu_items,
)
from netbox_nsm.objects.cot_routes import NSM_OBJECTS_GROUP_NAME


class NavigationObjectsMenuTests(SimpleTestCase):
    @patch("netbox_nsm.navigation_objects.iter_nsm_objects_menu_cots")
    def test_iter_yields_menu_item_for_nsm_objects_group_cot(self, iter_cots):
        cot = SimpleNamespace(
            slug="nsm_zone",
            group_name=NSM_OBJECTS_GROUP_NAME,
            get_verbose_name_plural=lambda: "Zones",
            get_model=lambda: SimpleNamespace(
                _meta=SimpleNamespace(model_name="table1model")
            ),
        )
        iter_cots.return_value = [cot]

        items = list(iter_nsm_object_menu_items())
        zone_items = [item for item in items if "Zones" in str(item.link_text)]
        self.assertEqual(len(zone_items), 1)
        self.assertIsInstance(zone_items[0], PluginMenuItem)
        self.assertIn("/plugins/netbox-nsm/objects/nsm_zone/", str(zone_items[0].url))
        self.assertNotIn("/plugins/custom-objects/", str(zone_items[0].url))

    @patch("netbox_nsm.navigation_objects.iter_nsm_objects_menu_cots")
    def test_iter_yields_menu_item_for_custom_group_cot(self, iter_cots):
        cot = SimpleNamespace(
            slug="nsm_custom_widget",
            group_name=NSM_OBJECTS_GROUP_NAME,
            get_verbose_name_plural=lambda: "Custom Widgets",
            get_model=lambda: SimpleNamespace(
                _meta=SimpleNamespace(model_name="table99model")
            ),
        )
        iter_cots.return_value = [cot]

        items = list(iter_nsm_object_menu_items())
        self.assertEqual(len(items), 1)
        self.assertIn("Custom Widgets", str(items[0].link_text))
        self.assertIn("/plugins/netbox-nsm/objects/nsm_custom_widget/", str(items[0].url))

    @patch("netbox_nsm.navigation_objects.iter_nsm_objects_menu_cots", return_value=[])
    def test_returns_empty_when_no_group_cots(self, _iter_cots):
        self.assertEqual(list(iter_nsm_object_menu_items()), [])

    @patch("netbox_nsm.navigation_objects.iter_nsm_object_menu_items")
    def test_build_group_returns_objects_label(self, iter_items):
        item = PluginMenuItem(link="plugins:netbox_nsm:setup", link_text="Zones")
        iter_items.return_value = [item]
        group = build_nsm_objects_menu_group()
        self.assertIsNotNone(group)
        label, items = group
        self.assertEqual(str(label), "Objects")
        self.assertEqual(items, (item,))

    @patch("netbox_nsm.navigation_objects.iter_nsm_object_menu_items", return_value=[])
    def test_build_group_returns_none_when_empty(self, _iter_items):
        self.assertIsNone(build_nsm_objects_menu_group())
