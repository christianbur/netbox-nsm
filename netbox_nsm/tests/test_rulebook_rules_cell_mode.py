"""Object cell display modes for Rules table cells."""

from netbox_nsm.rulebooks.cell_html import (
    CELL_MODE_COMPACT,
    CELL_MODE_INLINE,
    CELL_MODE_PILL_MORE,
    CELL_MODE_STACK,
    normalize_rules_cell_mode,
    render_rules_object_cell_html,
)
from netbox_nsm.rulebooks.rules_tab_base import parse_rules_cell_mode
from django.test import RequestFactory
from utilities.testing import TestCase


class RulesCellModeTests(TestCase):
    def test_normalize_rules_cell_mode(self):
        self.assertEqual(normalize_rules_cell_mode("inline"), CELL_MODE_INLINE)
        self.assertEqual(normalize_rules_cell_mode("compact"), CELL_MODE_COMPACT)
        self.assertEqual(normalize_rules_cell_mode("pill_more"), CELL_MODE_PILL_MORE)
        self.assertEqual(normalize_rules_cell_mode("stack"), CELL_MODE_STACK)
        self.assertEqual(normalize_rules_cell_mode("invalid"), CELL_MODE_STACK)
        self.assertEqual(normalize_rules_cell_mode(None), CELL_MODE_STACK)

    def test_parse_rules_cell_mode_from_request(self):
        request = RequestFactory().get("/rules/?cell_mode=inline")
        self.assertEqual(parse_rules_cell_mode(request), CELL_MODE_INLINE)
        request = RequestFactory().get("/rules/?cell_mode=pill_more")
        self.assertEqual(parse_rules_cell_mode(request), CELL_MODE_PILL_MORE)

    def test_render_stack_mode(self):
        items = [
            {"name": "DMZ", "url": "/a/", "color": "#f00"},
            {"name": "LAN", "url": "/b/", "color": "#0f0"},
        ]
        html = render_rules_object_cell_html(items, cell_mode=CELL_MODE_STACK)
        self.assertIn("nsm-ag-cell-list--stack", html)
        self.assertIn("DMZ", html)
        self.assertIn("LAN", html)
        self.assertNotIn("nsm-ag-cell-sep", html)

    def test_render_inline_mode(self):
        items = [
            {"name": "DMZ", "url": "/a/", "color": "#f00"},
            {"name": "LAN", "url": "/b/", "color": "#0f0"},
        ]
        html = render_rules_object_cell_html(items, cell_mode=CELL_MODE_INLINE)
        self.assertIn("nsm-ag-cell-list--inline", html)
        self.assertIn("nsm-ag-cell-sep", html)
        self.assertIn("DMZ", html)
        self.assertIn("LAN", html)

    def test_inline_mode_row_not_multiline_for_many_objects(self):
        row = {
            "cells_items": {
                "src_zones": [{"name": "a"}, {"name": "b"}, {"name": "c"}],
            },
            "system": {},
        }
        from netbox_nsm.rulebooks.rules_tab_base import _rules_row_is_multiline

        self.assertTrue(_rules_row_is_multiline(row, cell_mode=CELL_MODE_STACK))
        self.assertFalse(_rules_row_is_multiline(row, cell_mode=CELL_MODE_INLINE))

    def test_render_compact_single_item(self):
        items = [{"name": "DMZ", "url": "/a/", "color": "#f00"}]
        html = render_rules_object_cell_html(items, cell_mode=CELL_MODE_COMPACT)
        self.assertIn("DMZ", html)
        self.assertNotIn("nsm-ag-cell-counter", html)

    def test_render_compact_multiple_items(self):
        items = [
            {"name": "DMZ", "url": "/a/", "color": "#f00"},
            {"name": "LAN", "url": "/b/", "color": "#0f0"},
            {"name": "WAN", "url": "/c/", "color": "#00f"},
        ]
        html = render_rules_object_cell_html(items, cell_mode=CELL_MODE_COMPACT)
        self.assertIn("nsm-ag-cell-list--compact", html)
        self.assertIn("nsm-ag-cell-counter", html)
        self.assertIn("3 objects", html)
        self.assertIn('aria-label="3 objects"', html)
        self.assertIn('title="DMZ, LAN, WAN"', html)
        self.assertNotIn(">LAN<", html)

    def test_render_pill_more_single_item(self):
        items = [{"name": "DMZ", "url": "/a/", "color": "#f00"}]
        html = render_rules_object_cell_html(items, cell_mode=CELL_MODE_PILL_MORE)
        self.assertIn("DMZ", html)
        self.assertNotIn("nsm-ag-cell-more", html)

    def test_render_pill_more_multiple_items(self):
        items = [
            {"name": "DMZ", "url": "/a/", "color": "#f00"},
            {"name": "LAN", "url": "/b/", "color": "#0f0"},
            {"name": "WAN", "url": "/c/", "color": "#00f"},
        ]
        html = render_rules_object_cell_html(items, cell_mode=CELL_MODE_PILL_MORE)
        self.assertIn("nsm-ag-cell-list--pill-more", html)
        self.assertIn("DMZ", html)
        self.assertIn('class="nsm-ag-cell-item nsm-pill-hidden', html)
        self.assertIn(">+2<", html)
        self.assertIn("nsm-ag-cell-more", html)
        self.assertIn("classList.remove('nsm-pill-hidden')", html)

    def test_pill_more_mode_row_not_multiline_for_many_objects(self):
        row = {
            "cells_items": {
                "src_zones": [{"name": "a"}, {"name": "b"}, {"name": "c"}],
            },
            "system": {},
        }
        from netbox_nsm.rulebooks.rules_tab_base import _rules_row_is_multiline

        self.assertFalse(_rules_row_is_multiline(row, cell_mode=CELL_MODE_PILL_MORE))
