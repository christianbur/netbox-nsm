"""Tests for NSM object menu helpers (not wired into Security menu)."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from netbox.plugins import PluginMenuItem

from netbox_nsm.navigation_objects import (
    build_nsm_objects_menu_group,
    iter_nsm_object_menu_items,
)
from netbox_nsm.objects.nsm_config import merge_nsm_config_document_into_comments


class NavigationObjectsMenuTests(SimpleTestCase):
    @patch("netbox_nsm.navigation_objects.iter_nsm_objects_menu_cots")
    def test_iter_yields_menu_item_for_nsm_objects_group_cot(self, iter_cots):
        cot = SimpleNamespace(
            slug="nsm_zone",
            group_name="Legacy CO Group Name",
            comments=merge_nsm_config_document_into_comments("", {"menu": "objects"}),
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

    @patch("netbox_nsm.navigation_objects.iter_nsm_objects_menu_cots", return_value=[])
    def test_returns_empty_when_no_group_cots(self, _iter_cots):
        self.assertEqual(list(iter_nsm_object_menu_items()), [])

    @patch("netbox_nsm.navigation_objects.iter_nsm_object_menu_items")
    def test_build_group_returns_objects_label(self, iter_items):
        item = PluginMenuItem(link="plugins:netbox_nsm:bundles", link_text="Zones")
        iter_items.return_value = [item]
        group = build_nsm_objects_menu_group()
        self.assertIsNotNone(group)
        label, items = group
        self.assertEqual(str(label), "Objects")
        self.assertEqual(items, (item,))

    @patch("netbox_nsm.navigation_objects.iter_nsm_object_menu_items", return_value=[])
    def test_build_group_returns_none_when_empty(self, _iter_items):
        self.assertIsNone(build_nsm_objects_menu_group())
