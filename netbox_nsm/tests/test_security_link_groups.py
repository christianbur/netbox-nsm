"""Tests for Security Panel link table group metadata."""

from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.security.tab.links import prepare_link_tab_view
from netbox_nsm.security.tab.context import (
    finalize_link_type_group,
    finalize_link_type_groups,
    row_has_link_actions,
)

class RowHasLinkActionsTests(SimpleTestCase):
    def test_addr_analyzable_only(self):
        self.assertTrue(row_has_link_actions({"addr_analyzable": True}))

    def test_supports_addr_analysis_only(self):
        self.assertTrue(
            row_has_link_actions(
                {"supports_addr_analysis": True, "addr_analyzable": False}
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
                    "supports_addr_analysis": True,
                    "edit_url": "/plugins/netbox-nsm/object-link/1/edit/",
                    "delete_url": "/plugins/netbox-nsm/object-link/1/delete/",
                }
            ]
        )
        self.assertIn('class="btn-group btn-group-sm nsm-link-actions"', html)
        self.assertNotIn('data-col="actions"', html)
        self.assertIn("btn-light", html)
        self.assertIn("btn-warning", html)
        self.assertIn("btn-danger", html)
        self.assertIn("mdi-magnify text-dark", html)
        self.assertIn("mdi-pencil", html)
        self.assertIn("mdi-trash-can-outline", html)
        row_html = self._row(html)
        self.assertIn("demo-addr-0010", row_html)
        loupe_pos = row_html.index("nsm-ipa-loupe")
        edit_pos = row_html.index("btn-warning")
        delete_pos = row_html.index("btn-danger")
        self.assertLess(loupe_pos, edit_pos)
        self.assertLess(edit_pos, delete_pos)

    def test_loupe_only_for_analyzable_without_edit_delete(self):
        html = self._render(
            [
                {
                    "url": "/plugins/custom-objects/nsm_addresses/10/",
                    "name": "demo-addr-0010",
                    "ct_id": 99,
                    "obj_id": 10,
                    "addr_analyzable": True,
                    "supports_addr_analysis": True,
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
                    "supports_addr_analysis": False,
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
        self.assertIn("btn-danger", row_html)
        self.assertIn("mdi-trash-can-outline", row_html)

    def test_ipam_fk_row_shows_loupe_edit_and_delete(self):
        html = self._render(
            [
                {
                    "url": "/plugins/custom-objects/nsm_addresses/10/",
                    "name": "demo-addr-0010",
                    "ct_id": 99,
                    "obj_id": 10,
                    "addr_analyzable": True,
                    "supports_addr_analysis": True,
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
        self.assertIn('aria-label="Edit assignment"', row_html)
        self.assertIn("btn-danger", row_html)
        self.assertIn("mdi-trash-can-outline", row_html)

    def test_object_link_row_uses_edit_assignment_label(self):
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
        self.assertIn('aria-label="Edit assignment"', html)
        self.assertIn('aria-label="Remove assignment"', html)
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
                            "supports_addr_analysis": True,
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


class EnforcementPointPanelTemplateTests(SimpleTestCase):
    def test_renders_enforcement_point_root_with_nested_rulebooks(self):
        html = render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_panel_label": "Security",
                "nsm_security_badge": 1,
                "nsm_unique_rules_total": 0,
                "nsm_analyzer_url": "/analyzer/",
                "nsm_assign_url": "/assign/",
                "nsm_page_addr_analyzable": False,
                "nsm_link_table": None,
                "nsm_enforcement_point": {
                    "count": 1,
                    "add_url": "/rulebook-link/?ct_id=1&obj_id=2",
                    "rulebooks": [
                        {
                            "name": "Rulebook Demo",
                            "url": "/plugins/netbox-nsm/rulebooks/demo/",
                            "delete_url": "/enforcement-point/1/delete/",
                        }
                    ],
                },
                "nsm_api_url": "",
            },
        )
        enforced_pos = html.index('id="nsm-cat-enforced"')
        root_hdr = html[:enforced_pos]
        self.assertIn(">Enforcement Point<", root_hdr)
        self.assertNotIn(">Rulebook Demo<", root_hdr)
        self.assertIn(">Rulebooks<", html[enforced_pos:])
        self.assertIn(">Rulebook Demo<", html)
        self.assertIn("nsm-enforcement-rulebooks-table", html)
        self.assertIn("nsm-rb-hdr", html)
        self.assertNotIn('class="ps-3 py-2 text-muted">None', html)

    def test_hides_none_empty_state_when_enforcement_point_present(self):
        html = render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_panel_label": "Security",
                "nsm_security_badge": 1,
                "nsm_unique_rules_total": 0,
                "nsm_analyzer_url": "/analyzer/",
                "nsm_assign_url": "/assign/",
                "nsm_page_addr_analyzable": False,
                "nsm_link_table": None,
                "nsm_enforcement_point": {
                    "count": 1,
                    "add_url": None,
                    "rulebooks": [
                        {
                            "name": "Rulebook Demo",
                            "url": "/plugins/netbox-nsm/rulebooks/demo/",
                            "delete_url": None,
                        }
                    ],
                },
                "nsm_interface_analysis": [],
                "nsm_api_url": "",
            },
        )
        self.assertIn(">Enforcement Point<", html)
        self.assertNotIn('class="ps-3 py-2 text-muted">None', html)

    def test_hides_enforcement_point_section_when_empty(self):
        html = render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_panel_label": "Security",
                "nsm_security_badge": None,
                "nsm_unique_rules_total": 0,
                "nsm_analyzer_url": "/analyzer/",
                "nsm_assign_url": "/assign/",
                "nsm_page_addr_analyzable": False,
                "nsm_link_table": None,
                "nsm_enforcement_point": None,
                "nsm_api_url": "",
            },
        )
        self.assertNotIn('id="nsm-cat-enforced"', html)
        self.assertNotIn(">Enforcement Point<", html)
