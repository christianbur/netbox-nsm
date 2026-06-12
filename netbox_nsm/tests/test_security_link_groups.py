"""Tests for Security Panel link table group metadata."""

from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from netbox_nsm.template_content import (
    _finalize_link_type_group,
    _finalize_link_type_groups,
    _row_has_link_actions,
)


class RowHasLinkActionsTests(SimpleTestCase):
    def test_addr_analyzable_only(self):
        self.assertTrue(_row_has_link_actions({"addr_analyzable": True}))

    def test_supports_addr_analysis_only(self):
        self.assertTrue(
            _row_has_link_actions(
                {"supports_addr_analysis": True, "addr_analyzable": False}
            )
        )

    def test_edit_or_delete_only(self):
        self.assertTrue(_row_has_link_actions({"edit_url": "/edit/"}))
        self.assertTrue(_row_has_link_actions({"delete_url": "/delete/"}))

    def test_no_actions(self):
        self.assertFalse(_row_has_link_actions({}))
        self.assertFalse(_row_has_link_actions({"name": "prod"}))


class FinalizeLinkTypeGroupTests(SimpleTestCase):
    def test_show_actions_when_addr_analyzable_only(self):
        group = _finalize_link_type_group(
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
        group = _finalize_link_type_group(
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
        group = _finalize_link_type_group(
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
        group = _finalize_link_type_group(
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
        group = _finalize_link_type_group(
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

    def test_show_comment_column(self):
        group = _finalize_link_type_group(
            {
                "objects": [
                    {
                        "name": "zone-a",
                        "comment": "edge",
                    },
                    {"name": "zone-b"},
                ]
            }
        )
        self.assertTrue(group["show_comment"])

    def test_finalize_link_type_groups_preserves_order(self):
        groups = _finalize_link_type_groups(
            [
                {"type_key": "a", "objects": [{"addr_analyzable": True}]},
                {"type_key": "b", "objects": []},
            ]
        )
        self.assertEqual([g["type_key"] for g in groups], ["a", "b"])
        self.assertTrue(groups[0]["show_actions"])
        self.assertFalse(groups[1]["show_actions"])


class SecurityRulebookTreeTemplateTests(SimpleTestCase):
    def test_renders_rulebook_field_counts_without_rule_links(self):
        rb = SimpleNamespace(
            pk=5,
            name="Firewall",
            get_absolute_url=lambda: "/rulebooks/5/",
            get_rules_tab_url=lambda: "/rulebooks/5/rules/",
        )
        field = SimpleNamespace(pk=9, slug="source", name="Source")
        html = render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_panel_label": "Security",
                "nsm_security_badge": 1,
                "nsm_unique_rules_total": 1,
                "nsm_analyzer_url": "/analyzer/",
                "nsm_assign_url": "/assign/",
                "nsm_page_addr_analyzable": False,
                "nsm_rulebook_groups": [
                    {
                        "rulebook": rb,
                        "unique_count": 1,
                        "rules_tab_url": "/rulebooks/5/rules/",
                        "field_groups": [
                            {
                                "field": field,
                                "rule_count": 1,
                            }
                        ],
                    }
                ],
                "nsm_link_type_groups": [],
                "nsm_enforcer_assignments": [],
                "nsm_api_url": "/api/object-rules/?ct_id=1&obj_id=2",
            },
        )
        self.assertIn('id="nsm-cat-rulebook"', html)
        self.assertIn(">Rulebooks<", html)
        self.assertIn("nsm-rb-hdr", html)
        self.assertIn('data-rb-pk="5"', html)
        self.assertIn(">Firewall<", html)
        self.assertIn("/rulebooks/5/rules/", html)
        self.assertIn('id="nsm-rb-5-f-9"', html)
        self.assertIn(">Source<", html)
        self.assertNotIn("f_source__ct_", html)
        self.assertIn("nsm-rb-field-count", html)
        self.assertIn('class="nsm-rb-rule-list', html)
        self.assertIn('data-api-url="/api/object-rules/?ct_id=1&amp;obj_id=2"', html)
        self.assertIn('data-rb-pk="5"', html)
        self.assertIn('data-field-pk="9"', html)
        self.assertIn('data-loaded="0"', html)
        self.assertIn("nsm-rb-field-loading", html)
        self.assertIn("fetchFieldRules", html)
        self.assertNotIn('href="/rulebooks/5/rules/?f_name=rule1"', html)
        self.assertNotIn(">rule1<", html)
        self.assertIn('class="collapse nsm-rb-field-collapse"', html)
        self.assertNotIn("nsm-sentinel", html)
        self.assertNotIn("nsm-security-rulebook-header-links", html)

    def test_renders_dashed_separator_between_rulebooks_and_manual_links(self):
        rb = SimpleNamespace(
            pk=5,
            name="Firewall",
            get_absolute_url=lambda: "/rulebooks/5/",
            get_rules_tab_url=lambda: "/rulebooks/5/rules/",
        )
        field = SimpleNamespace(pk=9, slug="source", name="Source")
        html = render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_panel_label": "Security",
                "nsm_security_badge": 1,
                "nsm_unique_rules_total": 1,
                "nsm_analyzer_url": "/analyzer/",
                "nsm_assign_url": "/assign/",
                "nsm_page_addr_analyzable": False,
                "nsm_rulebook_groups": [
                    {
                        "rulebook": rb,
                        "unique_count": 1,
                        "rules_tab_url": "/rulebooks/5/rules/",
                        "field_groups": [
                            {
                                "field": field,
                                "rule_count": 1,
                            }
                        ],
                    }
                ],
                "nsm_link_type_groups": [
                    {
                        "type_key": "zone",
                        "type_label": "Zone",
                        "count": 1,
                        "show_comment": False,
                        "show_actions": True,
                        "objects": [
                            {
                                "name": "dmz",
                                "url": "/zones/1/",
                                "edit_url": "/edit/",
                                "delete_url": "/delete/",
                            }
                        ],
                    }
                ],
                "nsm_enforcer_assignments": [],
                "nsm_api_url": "/api/object-rules/?ct_id=1&obj_id=2",
            },
        )
        self.assertIn('<hr class="nsm-link-section-separator">', html)
        self.assertIn('id="nsm-cat-rulebook"', html)
        self.assertIn('id="nsm-cat-zone"', html)
        rulebook_pos = html.index('id="nsm-cat-rulebook"')
        separator_pos = html.index('<hr class="nsm-link-section-separator">')
        manual_pos = html.index('id="nsm-cat-zone"')
        self.assertLess(rulebook_pos, separator_pos)
        self.assertLess(separator_pos, manual_pos)

    def test_hides_separator_when_only_one_link_type_present(self):
        html = render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_panel_label": "Security",
                "nsm_security_badge": None,
                "nsm_analyzer_url": "/analyzer/",
                "nsm_assign_url": "/assign/",
                "nsm_page_addr_analyzable": False,
                "nsm_rulebook_groups": [],
                "nsm_link_type_groups": [
                    {
                        "type_key": "zone",
                        "type_label": "Zone",
                        "count": 1,
                        "show_comment": False,
                        "show_actions": False,
                        "objects": [{"name": "dmz", "url": "/zones/1/"}],
                    }
                ],
                "nsm_enforcer_assignments": [],
                "nsm_unique_rules_total": 0,
                "nsm_api_url": "",
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
            "nsm_rulebook_groups": [],
            "nsm_link_type_groups": [],
            "nsm_enforcer_assignments": [],
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
    def test_row_actions_use_btn_group_at_row_end(self):
        html = render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_panel_label": "Security",
                "nsm_security_badge": None,
                "nsm_analyzer_url": "/analyzer/",
                "nsm_assign_url": "/assign/",
                "nsm_page_addr_analyzable": False,
                "nsm_rulebook_groups": [],
                "nsm_link_type_groups": [
                    {
                        "type_key": "netbox_custom_objects__nsm_addresses",
                        "type_label": "Addresses",
                        "count": 1,
                        "show_comment": False,
                        "show_actions": True,
                        "objects": [
                            {
                                "url": "/plugins/custom-objects/nsm_addresses/10/",
                                "name": "demo-addr-0010",
                                "ct_id": 99,
                                "obj_id": 10,
                                "addr_analyzable": True,
                                "supports_addr_analysis": True,
                                "edit_url": "/plugins/netbox-nsm/object-link/1/edit/",
                                "delete_url": "/plugins/netbox-nsm/object-link/1/delete/",
                            }
                        ],
                    }
                ],
                "nsm_enforcer_assignments": [],
            },
        )
        self.assertIn('class="btn-group btn-group-sm nsm-link-actions"', html)
        self.assertIn('class="col-actions', html)
        self.assertIn("btn-light", html)
        self.assertIn("btn-warning", html)
        self.assertIn("btn-danger", html)
        self.assertIn("mdi-magnify text-dark", html)
        self.assertIn("mdi-pencil", html)
        self.assertIn("mdi-trash-can-outline", html)
        row_html = html.split('class="nsm-link-row"', 1)[1].split("</tr>", 1)[0]
        obj_cell, _, actions_cell = row_html.partition("</td>")
        self.assertIn("demo-addr-0010", obj_cell)
        self.assertIn("nsm-ipa-loupe", actions_cell)
        self.assertIn("btn-light", actions_cell)
        self.assertIn("mdi-magnify text-dark", actions_cell)
        self.assertIn("btn-warning", actions_cell)
        self.assertIn("mdi-pencil", actions_cell)
        self.assertIn("btn-danger", actions_cell)
        self.assertIn("mdi-trash-can-outline", actions_cell)
        loupe_pos = actions_cell.index("nsm-ipa-loupe")
        edit_pos = actions_cell.index("btn-warning")
        delete_pos = actions_cell.index("btn-danger")
        self.assertLess(loupe_pos, edit_pos)
        self.assertLess(edit_pos, delete_pos)

    def test_loupe_only_for_analyzable_without_edit_delete(self):
        html = render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_panel_label": "Security",
                "nsm_security_badge": None,
                "nsm_analyzer_url": "/analyzer/",
                "nsm_assign_url": "/assign/",
                "nsm_page_addr_analyzable": False,
                "nsm_rulebook_groups": [],
                "nsm_link_type_groups": [
                    {
                        "type_key": "netbox_custom_objects__nsm_addresses",
                        "type_label": "Addresses",
                        "count": 1,
                        "show_comment": False,
                        "show_actions": True,
                        "objects": [
                            {
                                "url": "/plugins/custom-objects/nsm_addresses/10/",
                                "name": "demo-addr-0010",
                                "ct_id": 99,
                                "obj_id": 10,
                                "addr_analyzable": True,
                                "supports_addr_analysis": True,
                            }
                        ],
                    }
                ],
                "nsm_enforcer_assignments": [],
            },
        )
        row_html = html.split('class="nsm-link-row"', 1)[1].split("</tr>", 1)[0]
        self.assertIn("nsm-ipa-loupe", row_html)
        self.assertIn("btn-light", row_html)
        self.assertIn("mdi-magnify text-dark", row_html)
        self.assertNotIn("btn-warning", row_html)
        self.assertNotIn("btn-danger", row_html)

    def test_edit_delete_without_loupe_for_non_analyzable(self):
        html = render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_panel_label": "Security",
                "nsm_security_badge": None,
                "nsm_analyzer_url": "/analyzer/",
                "nsm_assign_url": "/assign/",
                "nsm_page_addr_analyzable": False,
                "nsm_rulebook_groups": [],
                "nsm_link_type_groups": [
                    {
                        "type_key": "netbox_custom_objects__nsmzone",
                        "type_label": "Zones",
                        "count": 1,
                        "show_comment": False,
                        "show_actions": True,
                        "objects": [
                            {
                                "url": "/zones/1/",
                                "name": "prod",
                                "ct_id": 1,
                                "obj_id": 1,
                                "addr_analyzable": False,
                                "supports_addr_analysis": False,
                                "edit_url": "/plugins/netbox-nsm/object-link/2/edit/",
                                "delete_url": "/plugins/netbox-nsm/object-link/2/delete/",
                            }
                        ],
                    }
                ],
                "nsm_enforcer_assignments": [],
            },
        )
        row_html = html.split('class="nsm-link-row"', 1)[1].split("</tr>", 1)[0]
        self.assertNotIn("nsm-ipa-loupe", row_html)
        self.assertNotIn("mdi-magnify", row_html)
        self.assertIn("btn-warning", row_html)
        self.assertIn("mdi-pencil", row_html)
        self.assertIn("btn-danger", row_html)
        self.assertIn("mdi-trash-can-outline", row_html)

    def test_ipam_prefix_row_shows_loupe_edit_and_delete_without_typeconfig(self):
        """Prefix linked from address page: loupe via supports_addr_analysis."""
        html = render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_panel_label": "Security",
                "nsm_security_badge": None,
                "nsm_analyzer_url": "/analyzer/",
                "nsm_assign_url": "/assign/",
                "nsm_page_addr_analyzable": True,
                "nsm_rulebook_groups": [],
                "nsm_link_type_groups": [
                    {
                        "type_key": "ipam__prefix",
                        "type_label": "Prefix",
                        "count": 1,
                        "show_comment": False,
                        "show_actions": True,
                        "objects": [
                            {
                                "url": "/ipam/prefixes/5/",
                                "name": "10.245.10.0/24",
                                "ct_id": 14,
                                "obj_id": 5,
                                "addr_analyzable": False,
                                "supports_addr_analysis": True,
                                "edit_url": "/plugins/netbox-nsm/object-link/1/edit/",
                                "delete_url": "/plugins/netbox-nsm/object-link/1/delete/",
                            }
                        ],
                    }
                ],
                "nsm_enforcer_assignments": [],
            },
        )
        row_html = html.split('class="nsm-link-row"', 1)[1].split("</tr>", 1)[0]
        self.assertIn("nsm-ipa-loupe", row_html)
        self.assertIn("btn-light", row_html)
        self.assertIn("mdi-magnify text-dark", row_html)
        self.assertIn('data-ct="14"', row_html)
        self.assertIn('data-pk="5"', row_html)
        self.assertIn("btn-warning", row_html)
        self.assertIn("mdi-pencil", row_html)
        self.assertIn("btn-danger", row_html)
        self.assertIn("mdi-trash-can-outline", row_html)
        loupe_pos = row_html.index("nsm-ipa-loupe")
        edit_pos = row_html.index("btn-warning")
        delete_pos = row_html.index("btn-danger")
        self.assertLess(loupe_pos, edit_pos)
        self.assertLess(edit_pos, delete_pos)

    def test_ipam_fk_row_shows_loupe_edit_and_delete(self):
        html = render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_panel_label": "Security",
                "nsm_security_badge": None,
                "nsm_analyzer_url": "/analyzer/",
                "nsm_assign_url": "/assign/",
                "nsm_page_addr_analyzable": False,
                "nsm_rulebook_groups": [],
                "nsm_link_type_groups": [
                    {
                        "type_key": "netbox_custom_objects__nsm_addresses",
                        "type_label": "Addresses",
                        "count": 1,
                        "show_comment": False,
                        "show_actions": True,
                        "objects": [
                            {
                                "url": "/plugins/custom-objects/nsm_addresses/10/",
                                "name": "demo-addr-0010",
                                "ct_id": 99,
                                "obj_id": 10,
                                "addr_analyzable": True,
                                "supports_addr_analysis": True,
                                "edit_url": "/plugins/netbox-nsm/object-link/assign/?ct_id=234&obj_id=5&object_b_type_id=99&object_b_id=10&return_url=%2Fipam%2Fprefixes%2F5%2F",
                                "delete_url": "/plugins/netbox-nsm/panel-link/address-ipam-fk/nsm_addresses/clear/?field=prefix",
                            }
                        ],
                    }
                ],
                "nsm_enforcer_assignments": [],
            },
        )
        row_html = html.split('class="nsm-link-row"', 1)[1].split("</tr>", 1)[0]
        self.assertIn("col-actions", row_html)
        self.assertIn("nsm-ipa-loupe", row_html)
        self.assertIn("btn-light", row_html)
        self.assertIn("mdi-magnify text-dark", row_html)
        self.assertIn("btn-warning", row_html)
        self.assertIn("mdi-pencil", row_html)
        self.assertIn('aria-label="Edit assignment"', row_html)
        self.assertIn("btn-danger", row_html)
        self.assertIn("mdi-trash-can-outline", row_html)

    def test_object_link_row_uses_edit_assignment_label(self):
        html = render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_panel_label": "Security",
                "nsm_security_badge": None,
                "nsm_analyzer_url": "/analyzer/",
                "nsm_assign_url": "/assign/",
                "nsm_page_addr_analyzable": False,
                "nsm_rulebook_groups": [],
                "nsm_link_type_groups": [
                    {
                        "type_key": "netbox_custom_objects__nsmzone",
                        "type_label": "Zones",
                        "count": 1,
                        "show_comment": False,
                        "show_actions": True,
                        "objects": [
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
                    }
                ],
                "nsm_enforcer_assignments": [],
            },
        )
        self.assertIn('aria-label="Edit assignment"', html)
        self.assertIn('aria-label="Remove assignment"', html)
        self.assertIn('href="/plugins/netbox-nsm/object-link/2/edit/"', html)
        self.assertIn('href="/plugins/netbox-nsm/object-link/2/delete/"', html)


class SecurityLinkTableHeaderTests(SimpleTestCase):
    def _render_link_groups(self, groups):
        return render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_panel_label": "Security",
                "nsm_security_badge": None,
                "nsm_analyzer_url": "/analyzer/",
                "nsm_assign_url": "/assign/",
                "nsm_page_addr_analyzable": False,
                "nsm_rulebook_groups": [],
                "nsm_link_type_groups": groups,
                "nsm_enforcer_assignments": [],
            },
        )

    def test_typical_group_renders_no_thead(self):
        html = self._render_link_groups(
            [
                {
                    "type_key": "netbox_custom_objects__nsm_addresses",
                    "type_label": "Addresses",
                    "count": 1,
                    "show_comment": False,
                    "show_actions": True,
                    "objects": [
                        {
                            "url": "/plugins/custom-objects/nsm_addresses/10/",
                            "name": "demo-addr-0010",
                            "addr_analyzable": True,
                            "supports_addr_analysis": True,
                            "edit_url": "/edit/",
                            "delete_url": "/delete/",
                        }
                    ],
                }
            ]
        )
        table_html = html.split(
            'class="table table-hover table-sm mb-0 nsm-link-table"', 1
        )[1]
        self.assertNotIn("<thead", table_html)
        self.assertNotIn("col-object", table_html.split("<tbody", 1)[0])
        self.assertNotIn("LINK TYPE", html)
        self.assertNotIn("Link type", html)

    def test_comment_renders_inline_without_header(self):
        html = self._render_link_groups(
            [
                {
                    "type_key": "netbox_custom_objects__nsmzone",
                    "type_label": "Zones",
                    "count": 1,
                    "show_comment": True,
                    "show_actions": True,
                    "objects": [
                        {
                            "url": "/zones/1/",
                            "name": "prod",
                            "comment": "edge firewall",
                            "edit_url": "/edit/",
                            "delete_url": "/delete/",
                        }
                    ],
                }
            ]
        )
        table_html = html.split(
            'class="table table-hover table-sm mb-0 nsm-link-table"', 1
        )[1]
        self.assertNotIn("<thead", table_html)
        self.assertNotIn(">Comment<", table_html)
        row_html = html.split('class="nsm-link-row"', 1)[1].split("</tr>", 1)[0]
        self.assertIn('class="col-comment"', row_html)
        self.assertIn("edge firewall", row_html)
