"""Tests for rules-table IP Analyzer loupe rendering."""

import re
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from netbox_nsm.rulebooks.cell_html import (
    ipa_loupe_button_html,
    render_rules_cell_ag as _render_rules_cell_ag,
    render_rules_merged_object_cell_html,
)
from netbox_nsm.rulebooks.rules_tab import (
    _build_rules_cell_html,
    _inject_rules_cell_context_attrs,
)

class RulesCellLoupeTests(SimpleTestCase):
    def test_cell_loupe_once_for_analyzable_objects(self):
        html = _render_rules_cell_ag(
            [
                {
                    "url": "/a/1/",
                    "name": "net-a",
                    "color": "",
                    "ct": 1,
                    "pk": 2,
                    "addrAnalyzable": True,
                }
            ]
        )
        self.assertEqual(html.count("nsm-ipa-loupe"), 1)
        self.assertIn("nsm-ipa-cell-loupe", html)
        self.assertIn('data-addr-analyzable="1"', html)
        loupe_tag = re.search(r"<button[^>]*nsm-ipa-cell-loupe[^>]*>", html)
        self.assertIsNotNone(loupe_tag)
        self.assertNotIn("data-ct", loupe_tag.group(0))

    def test_cell_loupe_collects_all_objects_in_cell(self):
        html = _render_rules_cell_ag(
            [
                {
                    "url": "/a/1/",
                    "name": "net-a",
                    "color": "",
                    "ct": 1,
                    "pk": 2,
                    "addrAnalyzable": True,
                },
                {
                    "url": "/a/2/",
                    "name": "net-b",
                    "color": "",
                    "ct": 1,
                    "pk": 3,
                    "addrAnalyzable": True,
                },
            ]
        )
        self.assertEqual(html.count("nsm-ipa-loupe"), 1)
        self.assertEqual(html.count("nsm-ag-cell-item--probe"), 2)

    def test_cell_loupe_probe_and_visible_item_per_analyzable_object(self):
        """Stack/inline cells expose both probe markers and visible pills."""
        html = _render_rules_cell_ag(
            [
                {
                    "url": "/a/1/",
                    "name": "net-a",
                    "color": "",
                    "ct": 1,
                    "pk": 2,
                    "addrAnalyzable": True,
                }
            ]
        )
        self.assertEqual(html.count("nsm-ag-cell-item--probe"), 1)
        visible_matches = re.findall(
            r'<span class="nsm-ag-cell-item nsm-rules-filter-target[^"]*"([^>]*)>',
            html,
        )
        self.assertEqual(len(visible_matches), 1)
        attrs = visible_matches[0]
        self.assertIn('data-ct="1"', attrs)
        self.assertIn('data-pk="2"', attrs)
        self.assertIn('data-name="net-a"', attrs)
        self.assertIn('data-addr-analyzable="1"', attrs)

    def test_cell_loupe_skipped_for_non_analyzable_object(self):
        html = _render_rules_cell_ag(
            [{"url": "/a/1/", "name": "net-a", "color": "", "ct": 1, "pk": 2}]
        )
        self.assertNotIn("nsm-ipa-loupe", html)

    def test_inject_rules_cell_context_attrs_on_cell_list(self):
        base = _render_rules_cell_ag(
            [
                {
                    "url": "/a/1/",
                    "name": "net-a",
                    "color": "",
                    "ct": 1,
                    "pk": 2,
                    "addrAnalyzable": True,
                }
            ]
        )
        html = _inject_rules_cell_context_attrs(
            base,
            rule_index=44,
            rule_name="Allow Web",
            col_id="destination_addresses",
            col_position=5,
        )
        self.assertIn('data-rule-index="44"', html)
        self.assertIn('data-rule-name="Allow Web"', html)
        self.assertIn('data-col-id="destination_addresses"', html)
        self.assertIn('data-col-position="5"', html)

    def test_build_rules_object_cell_injects_context_attrs(self):
        class FakeRequest:
            GET = {}
            COOKIES = {}
            path = "/plugins/netbox_nsm/rulebooks/cot/demo/rules/"

            def get_full_path(self):
                return self.path

        col = {
            "kind": "object",
            "key": "destination_addresses",
            "col_id": "destination_addresses",
            "col_position": 5,
            "area_slug": "destination_addresses",
        }
        row = {
            "index": 44,
            "name": "Allow Web",
            "system": {"index": 44, "name": "Allow Web"},
            "cells_items": {
                "destination_addresses": [
                    {
                        "url": "/a/1/",
                        "name": "net-a",
                        "color": "",
                        "ct": 1,
                        "pk": 2,
                        "addrAnalyzable": True,
                    }
                ]
            },
        }
        html = _build_rules_cell_html(
            col,
            row,
            request=FakeRequest(),
            can_change=False,
            can_delete=False,
            object_fields_by_slug={},
        )
        self.assertIn('data-rule-index="44"', html)
        self.assertIn('data-rule-name="Allow Web"', html)
        self.assertIn('data-col-position="5"', html)

    def test_build_rules_expanded_address_column_merges_and_includes_cell_loupe(self):
        """Expanded address columns merge internally but keep IP Analyzer loupe + rule context."""
        class FakeRequest:
            GET = {}
            COOKIES = {}
            path = "/plugins/netbox_nsm/rulebooks/cot/demo/rules/"

            def get_full_path(self):
                return self.path

        col = {
            "kind": "object",
            "key": "destination_addresses",
            "col_id": "destination_addresses",
            "col_position": 3,
            "area_slug": "destination_addresses",
            "merged_keys": [
                "destination_addresses::address",
                "destination_addresses::address_group",
            ],
            "type_segments": [
                {
                    "key": "destination_addresses::address",
                    "type_label": "Address",
                },
                {
                    "key": "destination_addresses::address_group",
                    "type_label": "Address Group",
                },
            ],
            "is_polymorphic": True,
        }
        row = {
            "index": 12,
            "name": "Rule A",
            "system": {"index": 12, "name": "Rule A"},
            "cells_items": {
                "destination_addresses::address": [
                    {
                        "url": "/a/1/",
                        "name": "10.0.0.1",
                        "color": "",
                        "ct": 10,
                        "pk": 42,
                        "addrAnalyzable": True,
                    }
                ],
                "destination_addresses::address_group": [
                    {
                        "url": "/g/1/",
                        "name": "grp-net",
                        "color": "",
                        "ct": 11,
                        "pk": 7,
                        "addrAnalyzable": True,
                    }
                ],
            },
        }
        html = _build_rules_cell_html(
            col,
            row,
            request=FakeRequest(),
            can_change=False,
            can_delete=False,
            object_fields_by_slug={},
        )
        self.assertIn("merged_keys", col)
        self.assertIn("nsm-ipa-cell-loupe", html)
        self.assertIn("nsm-ag-cell-merged--has-loupe", html)
        self.assertNotIn("nsm-ag-cell-list--has-loupe", html)
        self.assertEqual(html.count("nsm-ipa-loupe"), 1)
        self.assertIn('data-rule-index="12"', html)
        self.assertIn('data-rule-name="Rule A"', html)
        self.assertIn('data-col-position="3"', html)
        self.assertIn('data-col-id="destination_addresses"', html)

    def test_ipa_loupe_button_html_includes_identity(self):
        html = ipa_loupe_button_html(
            ct=5, pk=9, name="demo", title="Objekt analysieren"
        )
        self.assertIn('data-ct="5"', html)
        self.assertIn('data-pk="9"', html)
        self.assertIn("Objekt analysieren", html)

    def test_merged_cell_loupe_once_for_analyzable_objects(self):
        html = render_rules_merged_object_cell_html(
            [
                {
                    "type_label": "Address",
                    "items": [
                        {
                            "url": "/a/1/",
                            "name": "bench-ip",
                            "color": "",
                            "ct": 1,
                            "pk": 2,
                            "addrAnalyzable": True,
                        }
                    ],
                },
            ],
            is_polymorphic=True,
        )
        self.assertIn("nsm-ag-cell-merged", html)
        self.assertIn("nsm-ag-cell-type-items", html)
        self.assertIn("nsm-ag-cell-link", html)
        self.assertEqual(html.count("nsm-ipa-loupe"), 1)
        self.assertIn("nsm-ipa-cell-loupe", html)
        self.assertIn("nsm-ag-cell-merged--has-loupe", html)
        self.assertNotIn("nsm-ag-cell-list--has-loupe", html)
        self.assertNotIn("nsm-ag-cell-list--item-loupe", html)
        self.assertIn('data-addr-analyzable="1"', html)

    def test_merged_cell_loupe_once_for_polymorphic_type_groups(self):
        html = render_rules_merged_object_cell_html(
            [
                {
                    "type_label": "Address",
                    "items": [
                        {
                            "url": "/a/1/",
                            "name": "bench-ip-1",
                            "color": "",
                            "ct": 1,
                            "pk": 2,
                            "addrAnalyzable": True,
                        }
                    ],
                },
                {
                    "type_label": "Address Group",
                    "items": [
                        {
                            "url": "/g/1/",
                            "name": "g-10.0.0.0/8",
                            "color": "",
                            "ct": 1,
                            "pk": 5,
                            "addrAnalyzable": True,
                        }
                    ],
                },
            ],
            is_polymorphic=True,
        )
        self.assertEqual(html.count("nsm-ipa-loupe"), 1)
        self.assertIn("nsm-ag-cell-merged--has-loupe", html)
        self.assertNotIn("nsm-ag-cell-list--has-loupe", html)
        self.assertEqual(html.count("nsm-ag-cell-type-group"), 2)
        self.assertEqual(html.count("nsm-ag-cell-item--probe"), 2)

    def test_merged_cell_loupe_once_for_multiple_addresses(self):
        items = [
            {
                "url": "/a/1/",
                "name": "ip-1",
                "color": "",
                "ct": 1,
                "pk": 2,
                "addrAnalyzable": True,
            },
            {
                "url": "/a/2/",
                "name": "ip-2",
                "color": "",
                "ct": 1,
                "pk": 3,
                "addrAnalyzable": True,
            },
        ]
        for is_polymorphic in (True, False):
            with self.subTest(is_polymorphic=is_polymorphic):
                html = render_rules_merged_object_cell_html(
                    [{"type_label": "Address", "items": items}],
                    is_polymorphic=is_polymorphic,
                )
                self.assertEqual(html.count("nsm-ipa-loupe"), 1)
                self.assertIn("nsm-ipa-cell-loupe", html)
                if is_polymorphic:
                    self.assertIn("nsm-ag-cell-merged--has-loupe", html)
                    self.assertNotIn("nsm-ag-cell-list--has-loupe", html)
                else:
                    self.assertIn("nsm-ag-cell-list--has-loupe", html)
                self.assertNotIn("nsm-ag-cell-list--item-loupe", html)
                self.assertNotRegex(
                    html,
                    r'ip-1</a><button[^>]*nsm-ipa-loupe',
                )
                self.assertNotRegex(
                    html,
                    r'ip-2</a><button[^>]*nsm-ipa-loupe',
                )

    def test_merged_cell_skips_loupe_for_non_analyzable_objects(self):
        html = render_rules_merged_object_cell_html(
            [
                {
                    "type_label": "Zone",
                    "items": [
                        {
                            "url": "/z/1/",
                            "name": "trust",
                            "color": "",
                            "ct": 1,
                            "pk": 2,
                        }
                    ],
                },
            ],
            is_polymorphic=True,
        )
        self.assertNotIn("nsm-ipa-loupe", html)

