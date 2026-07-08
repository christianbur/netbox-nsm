"""NSM object status indicators in rules cells and security panel."""

from types import SimpleNamespace

from django.test import SimpleTestCase

from netbox_nsm.core.nsm_object_status import (
    get_nsm_object_status,
    nsm_object_status_icon_html,
)
from netbox_nsm.rulebooks.cell_html import render_rules_object_cell_html


class NsmObjectStatusTests(SimpleTestCase):
    def test_active_status_has_no_icon(self):
        self.assertEqual(get_nsm_object_status(SimpleNamespace(status="active")), None)
        self.assertEqual(nsm_object_status_icon_html("active"), "")

    def test_deprecated_icon_is_red_info(self):
        html = nsm_object_status_icon_html("deprecated")
        self.assertIn("mdi-information-outline", html)
        self.assertIn("nsm-object-status-icon--deprecated", html)
        self.assertIn("color:#dc3545", html)

    def test_reserved_icon_is_orange_info(self):
        html = nsm_object_status_icon_html("reserved")
        self.assertIn("mdi-information-outline", html)
        self.assertIn("nsm-object-status-icon--reserved", html)

    def test_rules_cell_renders_status_icon(self):
        items = [
            {
                "url": "/zones/1/",
                "name": "old-zone",
                "color": "#f00",
                "status": "deprecated",
                "ct": 1,
                "pk": 1,
            }
        ]
        html = render_rules_object_cell_html(items, cell_mode="stack")
        self.assertIn("old-zone", html)
        self.assertIn("nsm-object-status-icon--deprecated", html)

    def test_rule_enabled_status_renders_checkmark_icons(self):
        from netbox_nsm.rulebooks.rules_tab.cells import _render_status_cell_html

        on_html = _render_status_cell_html(True)
        off_html = _render_status_cell_html(False)
        self.assertIn("mdi-check-bold", on_html)
        self.assertIn("text-success", on_html)
        self.assertNotIn("mdi-close-thick", on_html)
        self.assertIn("mdi-close-thick", off_html)
        self.assertIn("text-danger", off_html)
        self.assertNotIn("mdi-check-bold", off_html)
        self.assertNotIn("badge", on_html)
        self.assertNotIn("badge", off_html)


    def test_object_without_status_field_has_no_indicator(self):
        self.assertIsNone(get_nsm_object_status(SimpleNamespace(name="no-status")))

    def test_ipam_like_reserved_status(self):
        class _Status:
            value = "reserved"

        obj = SimpleNamespace(status=_Status())
        self.assertEqual(get_nsm_object_status(obj), "reserved")

    def test_non_indicator_status_values_ignored(self):
        self.assertIsNone(get_nsm_object_status(SimpleNamespace(status="dhcp")))
