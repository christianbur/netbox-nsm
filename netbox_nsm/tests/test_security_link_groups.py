"""Tests for Security Panel link table group metadata."""

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.security.tab.links import flatten_link_type_groups, prepare_link_tab_view
from netbox_nsm.security.tab.context import (
    finalize_link_type_group,
    finalize_link_type_groups,
    row_has_link_actions,
)

class RowHasLinkActionsTests(SimpleTestCase):
    def test_addr_analyzable_only(self):
        self.assertTrue(row_has_link_actions({"addr_analyzable": True}))

    def test_supports_addr_analyzer_only(self):
        self.assertTrue(
            row_has_link_actions(
                {"supports_addr_analyzer": True, "addr_analyzable": False}
            )
        )

    def test_edit_or_delete_only(self):
        self.assertTrue(row_has_link_actions({"edit_url": "/edit/"}))
        self.assertTrue(row_has_link_actions({"delete_url": "/delete/"}))

    def test_no_actions(self):
        self.assertFalse(row_has_link_actions({}))
        self.assertFalse(row_has_link_actions({"name": "prod"}))


class FinalizeLinkTypeGroupTests(SimpleTestCase):
    def test_show_actions_when_addr_analyzable_only(self):
        group = finalize_link_type_group(
            {
                "objects": [
                    {
                        "name": "addr-a",
                        "addr_analyzable": True,
                        "ct_id": 1,
                        "obj_id": 2,
                    }
                ]
            }
        )
        self.assertTrue(group["show_actions"])
        self.assertFalse(group["show_comment"])

    def test_show_actions_for_inherited_analyzable_without_delete(self):
        group = finalize_link_type_group(
            {
                "objects": [
                    {
                        "name": "10.0.0.0/8",
                        "addr_analyzable": True,
                        "inherited_from_name": "parent",
                    }
                ]
            }
        )
        self.assertTrue(group["show_actions"])

    def test_hide_actions_for_inherited_non_analyzable_without_delete(self):
        group = finalize_link_type_group(
            {
                "objects": [
                    {
                        "name": "prod",
                        "inherited_from_name": "parent",
                    }
                ]
            }
        )
        self.assertFalse(group["show_actions"])

    def test_show_actions_when_edit_or_delete_present(self):
        group = finalize_link_type_group(
            {
                "objects": [
                    {
                        "name": "zone-a",
                        "edit_url": "/edit/",
                        "delete_url": "/delete/",
                    }
                ]
            }
        )
        self.assertTrue(group["show_actions"])

    def test_show_actions_with_edit_only(self):
        group = finalize_link_type_group(
            {
                "objects": [
                    {
                        "name": "zone-a",
                        "edit_url": "/edit/",
                    }
                ]
            }
        )
        self.assertTrue(group["show_actions"])

    def test_show_field_via_payload(self):
        group = finalize_link_type_group(
            {
                "objects": [
                    {
                        "name": "zone-a",
                        "field_label": "source_zones",
                    },
                ]
            }
        )
        self.assertFalse(group["show_actions"])

    def test_finalize_link_type_groups_preserves_order(self):
        groups = finalize_link_type_groups(
            [
                {"type_key": "a", "objects": [{"addr_analyzable": True}]},
                {"type_key": "b", "objects": []},
            ]
        )
        self.assertEqual([g["type_key"] for g in groups], ["a", "b"])
        self.assertTrue(groups[0]["show_actions"])
        self.assertFalse(groups[1]["show_actions"])


class SecurityRulebookTreeTemplateTests(SimpleTestCase):
    def test_does_not_render_rulebook_tree(self):
        html = render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_panel_label": "Security",
                "nsm_security_badge": 1,
                "nsm_analyzer_url": "/analyzer/",
                "nsm_assign_url": "/assign/",
                "nsm_page_addr_analyzable": False,
                "nsm_link_table": None,
                "nsm_enforcement_point": None,
            },
        )
        self.assertNotIn('id="nsm-cat-rulebook"', html)
        self.assertNotIn("nsm-rulebook-accordion", html)
        self.assertNotIn("fetchFieldRules", html)
        self.assertNotIn(">Firewall<", html)
        self.assertNotIn(">Source<", html)

    def test_does_not_render_separator_between_rulebooks_and_links(self):
        html = render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_panel_label": "Security",
                "nsm_security_badge": 1,
                "nsm_analyzer_url": "/analyzer/",
                "nsm_assign_url": "/assign/",
                "nsm_page_addr_analyzable": False,
                **prepare_link_tab_view(
                    [
                        {
                            "type_key": "zone",
                            "type_label": "Zone",
                            "count": 1,
                            "show_actions": True,
                            "objects": [
                                {
                                    "name": "dmz",
                                    "url": "/zones/1/",
                                    "row_type_label": "Zone",
                                    "field_label": "Object link",
                                    "edit_url": "/edit/",
                                    "delete_url": "/delete/",
                                }
                            ],
                        }
                    ],
                    RequestFactory().get("/"),
                ),
                "nsm_enforcement_point": None,
            },
        )
        self.assertNotIn('id="nsm-cat-rulebook"', html)
        self.assertIn('id="nsm-link-objects"', html)
        self.assertNotIn('<hr class="nsm-link-section-separator">', html)

    def test_hides_separator_when_only_one_link_type_present(self):
        html = render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_panel_label": "Security",
                "nsm_security_badge": None,
                "nsm_analyzer_url": "/analyzer/",
                "nsm_assign_url": "/assign/",
                "nsm_page_addr_analyzable": False,
                "nsm_link_table": prepare_link_tab_view(
                    [
                        {
                            "type_key": "zone",
                            "type_label": "Zone",
                            "count": 1,
                            "show_actions": False,
                            "objects": [
                                {
                                    "name": "dmz",
                                    "url": "/zones/1/",
                                    "field_label": "Object link",
                                }
                            ],
                        }
                    ],
                    RequestFactory().get("/"),
                )["nsm_link_table"],
                "nsm_enforcement_point": None,
            },
        )
        self.assertNotIn('<hr class="nsm-link-section-separator">', html)


class SecurityPanelHeaderActionsTemplateTests(SimpleTestCase):
    def _render_header(self, **overrides):
        context = {
            "nsm_panel_label": "Security",
            "nsm_security_badge": None,
            "nsm_analyzer_url": "/plugins/netbox-nsm/object-analyzer/?ct=14&pk=5",
            "nsm_assign_url": "/assign/",
            "nsm_page_addr_analyzable": False,
            "nsm_link_table": None,
            "nsm_enforcement_point": None,
        }
        context.update(overrides)
        html = render_to_string("netbox_nsm/inc/security_links.html", context)
        return html.split('class="card-header', 1)[1].split("</h5>", 1)[0]

    def test_header_object_analyzer_is_icon_only(self):
        header = self._render_header()
        self.assertIn("mdi-graph-outline", header)
        self.assertIn('aria-label="Object Analyzer"', header)
        self.assertIn("btn-ghost-primary", header)
        self.assertNotIn("btn-ghost-secondary", header)
        self.assertNotIn(">Object Analyzer<", header)

    def test_header_shows_ip_loupe_for_addr_analyzable_page_object(self):
        header = self._render_header(
            nsm_page_addr_analyzable=True,
            nsm_page_object_ct=14,
            nsm_page_object_pk=5,
            nsm_page_object_name="10.245.10.0/24",
        )
        self.assertIn("mdi-graph-outline", header)
        self.assertIn("nsm-ipa-loupe", header)
        self.assertIn("btn-ghost-primary", header)
        self.assertNotIn("btn-light", header)
        self.assertIn("mdi-magnify", header)
        self.assertNotIn("mdi-magnify text-dark", header)
        self.assertIn('data-ct="14"', header)
        self.assertIn('data-pk="5"', header)
        self.assertIn('data-name="10.245.10.0/24"', header)

    def test_header_hides_ip_loupe_for_non_addr_analyzable_page_object(self):
        header = self._render_header(nsm_page_addr_analyzable=False)
        self.assertIn("mdi-graph-outline", header)
        self.assertNotIn("nsm-ipa-loupe", header)
        self.assertNotIn("mdi-magnify", header)


class SecurityLinkRowActionsTemplateTests(SimpleTestCase):
    """Linked-object rows keep analyze / edit / delete actions."""

    def _render(self, objects, *, type_key="netbox_custom_objects__nsm_addresses", type_label="Addresses"):
        ctx = prepare_link_tab_view(
            [{"type_key": type_key, "type_label": type_label, "objects": objects, "show_actions": True}],
            RequestFactory().get("/"),
        )
        return render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_panel_label": "Security",
                "nsm_security_badge": None,
                "nsm_analyzer_url": "/analyzer/",
                "nsm_assign_url": "/assign/",
                "nsm_page_addr_analyzable": False,
                "nsm_enforcement_point": None,
                **ctx,
            },
        )

    def _row(self, html):
        return html.split('class="nsm-link-row"', 1)[1].split("</tr>", 1)[0]

    def test_row_actions_use_btn_group_at_row_end(self):
        html = self._render(
            [
                {
                    "url": "/plugins/custom-objects/nsm_addresses/10/",
                    "name": "demo-addr-0010",
                    "ct_id": 99,
                    "obj_id": 10,
                    "addr_analyzable": True,
                    "supports_addr_analyzer": True,
                    "edit_url": "/plugins/netbox-nsm/object-link/1/edit/",
                    "delete_url": "/plugins/netbox-nsm/object-link/1/delete/",
                }
            ]
        )
        self.assertIn('class="btn-group btn-group-sm nsm-link-actions"', html)
        self.assertNotIn('data-col="actions"', html)
        self.assertIn("btn-light", html)
        self.assertIn("btn-warning", html)
        self.assertIn("dropdown-toggle-split", html)
        self.assertIn("mdi-magnify text-dark", html)
        self.assertIn("mdi-pencil", html)
        self.assertIn("mdi-trash-can-outline", html)
        row_html = self._row(html)
        self.assertIn("demo-addr-0010", row_html)
        self.assertIn("dropdown-menu", row_html)
        self.assertNotIn('class="btn btn-danger btn-sm"', row_html)
        loupe_pos = row_html.index("nsm-ipa-loupe")
        edit_pos = row_html.index("nsm-link-edit-menu")
        self.assertLess(loupe_pos, edit_pos)

    def test_loupe_only_for_analyzable_without_edit_delete(self):
        html = self._render(
            [
                {
                    "url": "/plugins/custom-objects/nsm_addresses/10/",
                    "name": "demo-addr-0010",
                    "ct_id": 99,
                    "obj_id": 10,
                    "addr_analyzable": True,
                    "supports_addr_analyzer": True,
                }
            ]
        )
        row_html = self._row(html)
        self.assertIn("nsm-ipa-loupe", row_html)
        self.assertIn("btn-light", row_html)
        self.assertIn("mdi-magnify text-dark", row_html)
        self.assertNotIn("btn-warning", row_html)
        self.assertNotIn("btn-danger", row_html)

    def test_edit_delete_without_loupe_for_non_analyzable(self):
        html = self._render(
            [
                {
                    "url": "/zones/1/",
                    "name": "prod",
                    "ct_id": 1,
                    "obj_id": 1,
                    "addr_analyzable": False,
                    "supports_addr_analyzer": False,
                    "edit_url": "/plugins/netbox-nsm/object-link/2/edit/",
                    "delete_url": "/plugins/netbox-nsm/object-link/2/delete/",
                }
            ],
            type_key="netbox_custom_objects__nsmzone",
            type_label="Zones",
        )
        row_html = self._row(html)
        self.assertNotIn("nsm-ipa-loupe", row_html)
        self.assertNotIn("mdi-magnify", row_html)
        self.assertIn("btn-warning", row_html)
        self.assertIn("mdi-pencil", row_html)
        self.assertIn("dropdown-toggle-split", row_html)
        self.assertIn("Remove assignment", row_html)
        self.assertIn("mdi-trash-can-outline", row_html)
        self.assertNotIn('class="btn btn-danger btn-sm"', row_html)

    def test_cot_row_uses_same_button_group_as_object_links(self):
        html = self._render(
            [
                {
                    "url": "/plugins/custom-objects/nsm_address_group/5/",
                    "name": "demo-addr-group-008",
                    "ct_id": 99,
                    "obj_id": 5,
                    "is_cot_row": True,
                    "cot_slug": "nsm_address_group",
                    "supports_addr_analyzer": True,
                    "edit_url": "/plugins/netbox_custom_objects/customobject/nsm_address_group/5/edit/",
                    "delete_url": "/plugins/netbox_custom_objects/customobject/nsm_address_group/5/delete/",
                    "changelog_url": "/plugins/netbox_custom_objects/customobject/nsm_address_group/5/changelog/",
                }
            ],
            type_key="netbox_custom_objects__nsm_address_group",
            type_label="Address Group",
        )
        row_html = self._row(html)
        self.assertIn('class="btn-group btn-group-sm nsm-link-actions"', row_html)
        self.assertIn("dropdown-toggle-split", row_html)
        self.assertIn("nsm-ipa-loupe", row_html)
        self.assertIn("mdi-pencil", row_html)
        self.assertIn("mdi-history", row_html)
        self.assertIn("mdi-trash-can-outline", row_html)
        self.assertIn("Changelog", row_html)
        self.assertIn("Delete", row_html)
        self.assertNotIn('class="btn btn-danger btn-sm"', row_html)

    def test_ipam_fk_row_shows_loupe_edit_and_delete(self):
        html = self._render(
            [
                {
                    "url": "/plugins/custom-objects/nsm_addresses/10/",
                    "name": "demo-addr-0010",
                    "ct_id": 99,
                    "obj_id": 10,
                    "addr_analyzable": True,
                    "supports_addr_analyzer": True,
                    "source": "ipam_fk",
                    "source_label": "IPAM",
                    "edit_url": "/plugins/netbox-nsm/object-link/assign/?ct_id=234",
                    "delete_url": "/plugins/netbox-nsm/panel-link/address-ipam-fk/nsm_addresses/clear/?field=prefix",
                }
            ]
        )
        row_html = self._row(html)
        self.assertIn("nsm-ipa-loupe", row_html)
        self.assertIn("btn-light", row_html)
        self.assertIn("mdi-magnify text-dark", row_html)
        self.assertIn("btn-warning", row_html)
        self.assertIn('aria-label="Edit"', row_html)
        self.assertIn("dropdown-toggle-split", row_html)
        self.assertIn("Remove assignment", row_html)
        self.assertIn("mdi-trash-can-outline", row_html)
        self.assertNotIn('class="btn btn-danger btn-sm"', row_html)

    def test_object_link_row_uses_edit_and_delete_labels(self):
        html = self._render(
            [
                {
                    "url": "/zones/1/",
                    "name": "prod",
                    "ct_id": 1,
                    "obj_id": 1,
                    "addr_analyzable": False,
                    "edit_url": "/plugins/netbox-nsm/object-link/2/edit/",
                    "delete_url": "/plugins/netbox-nsm/object-link/2/delete/",
                }
            ],
            type_key="netbox_custom_objects__nsmzone",
            type_label="Zones",
        )
        self.assertIn('aria-label="Edit"', html)
        self.assertIn("dropdown-toggle-split", html)
        self.assertIn("Remove assignment", html)
        self.assertIn('href="/plugins/netbox-nsm/object-link/2/edit/"', html)
        self.assertIn('href="/plugins/netbox-nsm/object-link/2/delete/"', html)


class SecurityLinkTableTests(SimpleTestCase):
    """Linked objects use a flat PR #482-style table."""

    def _render_link_groups(self, groups):
        ctx = prepare_link_tab_view(groups, RequestFactory().get("/"))
        return render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_panel_label": "Security",
                "nsm_security_badge": None,
                "nsm_analyzer_url": "/analyzer/",
                "nsm_assign_url": "/assign/",
                "nsm_page_addr_analyzable": False,
                "nsm_enforcement_point": None,
                **ctx,
            },
        )

    def test_renders_flat_table_with_controls(self):
        html = self._render_link_groups(
            [
                {
                    "type_key": "netbox_custom_objects__nsm_addresses",
                    "type_label": "Addresses",
                    "objects": [
                        {
                            "url": "/plugins/custom-objects/nsm_addresses/10/",
                            "name": "demo-addr-0010",
                            "field_label": "Object link",
                            "supports_addr_analyzer": True,
                            "edit_url": "/edit/",
                            "delete_url": "/delete/",
                        }
                    ],
                }
            ]
        )
        self.assertNotIn('class="nav nav-tabs nsm-link-tabs"', html)
        self.assertNotIn('class="nsm-link-value-filter', html)
        self.assertIn("Quick search", html)
        self.assertIn("object-list", html)
        thead = html.split("<thead", 1)[1].split("<tbody", 1)[0]
        self.assertIn("Type", thead)
        self.assertIn("Object", thead)
        self.assertIn("Value", thead)
        self.assertIn("Field", thead)
        self.assertIn("demo-addr-0010", html)
        self.assertIn("Object link", html)

    def test_field_column_shows_link_source_labels(self):
        html = self._render_link_groups(
            [
                {
                    "type_key": "ipam__ipaddress",
                    "type_label": "IP Addresses",
                    "objects": [
                        {
                            "name": "10.0.0.1/32",
                            "url": "/x",
                            "row_type_label": "IP Addresses",
                            "field_label": "prefix",
                        },
                        {
                            "name": "grp",
                            "url": "/y",
                            "row_type_label": "IP Addresses",
                            "field_label": "Member of",
                        },
                    ],
                }
            ]
        )
        self.assertIn("prefix", html)
        self.assertIn("Member of", html)

    def test_value_and_field_columns_allow_text_wrapping(self):
        html = self._render_link_groups(
            [
                {
                    "type_key": "netbox_custom_objects__nsm_addresses",
                    "type_label": "Addresses",
                    "objects": [
                        {
                            "url": "/x/",
                            "name": "addr-1",
                            "row_type_label": "Addresses",
                            "value_label": "alpha, beta, gamma",
                            "field_label": "Object link",
                        }
                    ],
                }
            ]
        )
        self.assertIn("white-space: normal", html)
        self.assertIn("overflow-wrap: break-word", html)
        self.assertIn(".col-value", html)
        self.assertIn(".col-field", html)
        self.assertIn(".col-object", html)
        self.assertNotIn("max-width: 18rem", html)

    def test_type_column_allows_wrapping(self):
        html = self._render_link_groups(
            [
                {
                    "type_key": "k",
                    "type_label": "Rulebook RB Demo Zone/Address",
                    "objects": [
                        {
                            "url": "/x/",
                            "name": "rule-1",
                            "row_type_label": "Rulebook RB Demo Zone/Address",
                            "field_label": "x",
                        }
                    ],
                }
            ]
        )
        marker = ".nsm-link-objects table.nsm-link-table .col-type"
        idx = html.index(marker)
        block = html[idx : idx + 260]
        self.assertIn("white-space: normal", block)
        self.assertNotIn("white-space: nowrap", block.split(".col-object")[0].split(marker, 1)[1])

    def test_object_column_allows_wrapping(self):
        html = self._render_link_groups(
            [
                {
                    "type_key": "netbox_custom_objects__nsm_addresses",
                    "type_label": "Addresses",
                    "objects": [{"url": "/x/", "name": "addr-1", "field_label": "x"}],
                }
            ]
        )
        marker = ".nsm-link-objects table.nsm-link-table .col-object"
        self.assertIn(marker, html)
        idx = html.index(marker)
        block = html[idx : idx + 280]
        self.assertIn("white-space: normal", block)

    def test_per_row_type_label_preserved_over_group_label(self):
        readable = "Rulebook RB Demo Zone/Address"
        html = self._render_link_groups(
            [
                {
                    "type_key": "netbox_custom_objects__nsm_rb_demo",
                    "type_label": "nsm_rb_demo_zone_addresses",
                    "objects": [
                        {
                            "url": "/x/",
                            "name": "rule-1",
                            "row_type_label": readable,
                            "row_type_filter_key": "nsm_rb_demo_zone_addresses",
                            "cot_slug": "nsm_rb_demo_zone_addresses",
                            "field_label": "Addresses (Source)",
                        }
                    ],
                }
            ]
        )
        self.assertIn(readable, html)
        self.assertNotIn(">nsm_rb_demo_zone_addresses<", html)

    def test_type_column_links_to_type_list_or_filter(self):
        from unittest.mock import patch

        with patch(
            "netbox_nsm.security.tab.links.build_row_type_url",
            return_value="/ipam/ip-addresses/",
        ):
            html = self._render_link_groups(
                [
                    {
                        "type_key": "ipam__ipaddress",
                        "type_label": "IP addresses",
                        "objects": [
                            {
                                "url": "/ipam/ip-addresses/1/",
                                "name": "10.0.0.1/32",
                                "ct_id": 69,
                                "row_type_label": "IP addresses",
                                "row_type_filter_key": "ipam__ipaddress",
                                "field_label": "",
                            }
                        ],
                    }
                ]
            )
        self.assertIn('href="/ipam/ip-addresses/"', html)
        self.assertIn("IP addresses</a>", html)

    def test_type_column_links_cot_list_by_slug(self):
        from unittest.mock import patch

        with patch(
            "netbox_nsm.security.tab.links.build_row_type_url",
            return_value="/plugins/netbox-nsm/objects/nsm_address_group/",
        ):
            html = self._render_link_groups(
                [
                    {
                        "type_key": "netbox_custom_objects__nsm_address_group",
                        "type_label": "Address Group",
                        "objects": [
                            {
                                "url": "/plugins/netbox-nsm/objects/nsm_address_group/1/",
                                "name": "demo-group",
                                "ct_id": 1,
                                "cot_slug": "nsm_address_group",
                                "row_type_label": "Address Group",
                                "row_type_filter_key": "nsm_address_group",
                                "field_label": "Group Members",
                            }
                        ],
                    }
                ]
            )
        self.assertIn(
            'href="/plugins/netbox-nsm/objects/nsm_address_group/"',
            html,
        )

    def test_renders_full_value_label_and_long_field_text(self):
        long_value = "slug-a, slug-b, slug-c, slug-d, slug-e"
        long_field = "Address (this object -> remote endpoint)"
        html = self._render_link_groups(
            [
                {
                    "type_key": "netbox_custom_objects__nsm_addresses",
                    "type_label": "Addresses",
                    "objects": [
                        {
                            "url": "/x/",
                            "name": "addr-1",
                            "row_type_label": "Addresses",
                            "value_label": long_value,
                            "value_key": long_value,
                            "field_label": long_field,
                        }
                    ],
                }
            ]
        )
        self.assertIn(long_value, html)
        self.assertIn("Address (this object", html)
        self.assertIn("remote endpoint)", html)

    def test_value_column_renders_linked_items(self):
        html = self._render_link_groups(
            [
                {
                    "type_key": "netbox_custom_objects__nsm_addresses",
                    "type_label": "Addresses",
                    "objects": [
                        {
                            "url": "/x/",
                            "name": "rule-1",
                            "row_type_label": "Addresses",
                            "value_key": "alpha, beta",
                            "value_label": "alpha, beta",
                            "value_items": [
                                {"label": "alpha", "url": "/alpha/"},
                                {"label": "beta", "url": "/beta/"},
                            ],
                            "field_label": "Addresses (Source)",
                        }
                    ],
                }
            ]
        )
        self.assertIn('href="/alpha/"', html)
        self.assertIn('href="/beta/"', html)
        self.assertIn(">alpha</a>", html)
        self.assertIn(">beta</a>", html)


class BuildRowTypeUrlTests(SimpleTestCase):
    def test_rulebook_slug_links_to_rulebook_detail(self):
        from unittest.mock import MagicMock, patch

        from netbox_nsm.security.tab.links import build_row_type_url

        with patch(
            "netbox_nsm.rulebooks.registry.get_deployed_cot_rulebook",
            return_value=MagicMock(),
        ), patch(
            "netbox_nsm.rulebooks.virtual_cot.VirtualCotRulebook.get_absolute_url",
            return_value="/plugins/netbox-nsm/rulebooks/cot/nsm_rb_demo/",
        ):
            url = build_row_type_url(
                {
                    "row_type_filter_key": "nsm_rb_demo_zone_addresses",
                    "cot_slug": "nsm_rb_demo_zone_addresses",
                },
                request=None,
                filter_url="?nsm_ty=nsm_rb_demo_zone_addresses",
                ct_cache={},
            )
        self.assertEqual(url, "/plugins/netbox-nsm/rulebooks/cot/nsm_rb_demo/")

    def test_falls_back_to_type_filter_url(self):
        from netbox_nsm.security.tab.links import build_row_type_url

        url = build_row_type_url(
            {"row_type_filter_key": "unknown__type"},
            request=None,
            filter_url="?nsm_ty=unknown__type",
            ct_cache={},
        )
        self.assertEqual(url, "?nsm_ty=unknown__type")


class TypeConfigDisplayNameTests(SimpleTestCase):
    def test_verbose_name_plural_preserves_ip_acronym(self):
        from unittest.mock import MagicMock

        from netbox_nsm.core.display_utils import type_config_display_name

        ct = MagicMock()
        model = MagicMock()
        model._meta.verbose_name_plural = "IP addresses"
        ct.model_class.return_value = model

        self.assertEqual(type_config_display_name(None, ct), "IP addresses")

    def test_verbose_name_plural_preserves_german_ip_label(self):
        from unittest.mock import MagicMock

        from netbox_nsm.core.display_utils import type_config_display_name

        ct = MagicMock()
        model = MagicMock()
        model._meta.verbose_name_plural = "IP-Adressen"
        ct.model_class.return_value = model

        self.assertEqual(type_config_display_name(None, ct), "IP-Adressen")


class SecurityRowsListValueTests(SimpleTestCase):
    def test_flatten_preserves_per_row_type_metadata(self):
        rows = flatten_link_type_groups(
            [
                {
                    "type_key": "netbox_custom_objects__nsm_rb_demo",
                    "type_label": "nsm_rb_demo_zone_addresses",
                    "objects": [
                        {
                            "name": "rule-1",
                            "row_type_label": "Rulebook RB Demo Zone/Address",
                            "row_type_filter_key": "nsm_rb_demo_zone_addresses",
                        }
                    ],
                }
            ]
        )
        self.assertEqual(rows[0]["row_type_label"], "Rulebook RB Demo Zone/Address")
        self.assertEqual(rows[0]["row_type_filter_key"], "nsm_rb_demo_zone_addresses")

    def test_cot_type_display_label_prefers_rulebook_verbose_name(self):
        from netbox_nsm.security.tab.security_rows import _cot_type_display_label

        class Cot:
            slug = "nsm_rb_demo_zone_addresses"
            verbose_name = "Rulebook RB Demo Zone/Address"
            name = "nsm_rb_demo_zone_addresses"

        self.assertEqual(
            _cot_type_display_label(Cot()),
            "Rulebook RB Demo Zone/Address",
        )

    def test_get_field_value_returns_all_multiobject_members(self):
        from unittest.mock import MagicMock

        from netbox_custom_objects.choices import CustomFieldTypeChoices

        from netbox_nsm.security.tab.combined import _get_field_value

        members = [object() for _ in range(6)]
        manager = MagicMock()
        manager.all.return_value = members

        field = MagicMock()
        field.is_junction_row = False
        field.type = CustomFieldTypeChoices.TYPE_MULTIOBJECT
        field.name = "addresses"

        obj = MagicMock()
        obj.addresses = manager

        self.assertEqual(_get_field_value(obj, field), members)

    def test_list_value_key_label_joins_all_items(self):
        from netbox_nsm.security.tab.security_rows import _list_value_key_label

        key, label = _list_value_key_label(["a", "b", "c", "d"])
        self.assertEqual(label, "a, b, c, d")
        self.assertEqual(key, "a, b, c, d")

    def test_apply_field_value_builds_linked_items(self):
        from unittest.mock import MagicMock

        from netbox_nsm.security.tab.security_rows import _apply_field_value

        obj_a = MagicMock()
        obj_a.__str__ = lambda self: "demo-a"
        obj_a.get_absolute_url.return_value = "/a/"
        obj_b = MagicMock()
        obj_b.__str__ = lambda self: "demo-b"
        obj_b.get_absolute_url.return_value = "/b/"

        key, label, items = _apply_field_value([obj_a, obj_b])
        self.assertEqual(label, "demo-a, demo-b")
        self.assertEqual(
            items,
            [{"label": "demo-a", "url": "/a/"}, {"label": "demo-b", "url": "/b/"}],
        )
        self.assertEqual(key, label)

    def test_list_value_key_label_empty_list_uses_ungrouped(self):
        from netbox_nsm.security.tab.security_rows import _list_value_key_label
        from netbox_nsm.security.tab.value_groups import UNGROUPED_KEY

        key, label = _list_value_key_label([])
        self.assertEqual(label, "")
        self.assertEqual(key, UNGROUPED_KEY)
