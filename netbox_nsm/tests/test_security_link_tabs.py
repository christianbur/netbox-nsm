"""Tests for Security tab object-type tabs + value sub-grouping + pagination."""

from __future__ import annotations

from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.security.tab.links import (
    DEFAULT_PER_PAGE,
    build_value_subgroups,
    prepare_link_tab_view,
)
from netbox_nsm.security.tab.value_groups import (
    UNGROUPED_KEY,
    UNGROUPED_LABEL,
    nsm_object_group_value,
)


def _obj(name, value_key="_none", value_label="—"):
    return {
        "name": name,
        "url": f"/o/{name}/",
        "value_key": value_key,
        "value_label": value_label,
    }


def _group(type_key, label, objects, **extra):
    base = {
        "type_key": type_key,
        "type_label": label,
        "count": len(objects),
        "objects": objects,
        "show_comment": False,
        "show_actions": False,
    }
    base.update(extra)
    return base


class NsmObjectGroupValueTests(SimpleTestCase):
    def test_value_attribute_used(self):
        obj = SimpleNamespace(value="Permit")
        self.assertEqual(nsm_object_group_value(obj), ("Permit", "Permit"))

    def test_choice_display_preferred_as_label(self):
        obj = SimpleNamespace(action="permit", get_action_display=lambda: "Permit")
        self.assertEqual(nsm_object_group_value(obj), ("permit", "Permit"))

    def test_falls_back_to_ungrouped(self):
        obj = SimpleNamespace(name="addr-1")
        self.assertEqual(nsm_object_group_value(obj), (UNGROUPED_KEY, UNGROUPED_LABEL))

    def test_empty_string_value_is_ignored(self):
        obj = SimpleNamespace(value="   ")
        self.assertEqual(nsm_object_group_value(obj), (UNGROUPED_KEY, UNGROUPED_LABEL))


class BuildValueSubgroupsTests(SimpleTestCase):
    def test_counts_per_value_and_ungrouped_last(self):
        objects = [
            _obj("a", "Permit", "Permit"),
            _obj("b", "Deny", "Deny"),
            _obj("c", "Permit", "Permit"),
            _obj("d"),
        ]
        subgroups = build_value_subgroups(objects)
        by_key = {sg["value_key"]: sg["count"] for sg in subgroups}
        self.assertEqual(by_key, {"Permit": 2, "Deny": 1, UNGROUPED_KEY: 1})
        self.assertEqual(subgroups[-1]["value_key"], UNGROUPED_KEY)

    def test_single_value_yields_one_subgroup(self):
        subgroups = build_value_subgroups([_obj("a", "Permit", "Permit")])
        self.assertEqual(len(subgroups), 1)


class PrepareLinkTabViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _ctx(self, query=""):
        request = self.factory.get(f"/dcim/devices/1/security/{query}")
        groups = [
            _group(
                "co__action",
                "Action",
                [
                    _obj("act-permit-1", "Permit", "Permit"),
                    _obj("act-deny-1", "Deny", "Deny"),
                    _obj("act-permit-2", "Permit", "Permit"),
                ],
            ),
            _group("ipam__prefix", "Prefix", [_obj("10.0.0.0/8")]),
        ]
        return prepare_link_tab_view(groups, request)

    def test_first_group_active_by_default(self):
        ctx = self._ctx()
        self.assertEqual(ctx["nsm_active_link_type"], "co__action")
        active = next(g for g in ctx["nsm_link_type_groups"] if g["is_active"])
        self.assertTrue(active["paginated"])
        self.assertTrue(active["has_value_grouping"])
        self.assertEqual(len(active["page"]), 3)

    def test_requested_type_becomes_active(self):
        ctx = self._ctx("?nsm_lt=ipam__prefix")
        self.assertEqual(ctx["nsm_active_link_type"], "ipam__prefix")
        active = next(g for g in ctx["nsm_link_type_groups"] if g["is_active"])
        self.assertEqual(len(active["page"]), 1)
        self.assertFalse(active["has_value_grouping"])

    def test_value_filter_restricts_page(self):
        ctx = self._ctx("?nsm_lt=co__action&nsm_lv=Permit")
        self.assertEqual(ctx["nsm_active_link_value"], "Permit")
        active = next(g for g in ctx["nsm_link_type_groups"] if g["is_active"])
        self.assertEqual(len(active["page"]), 2)
        self.assertTrue(all(o["value_key"] == "Permit" for o in active["page"]))

    def test_unknown_value_ignored(self):
        ctx = self._ctx("?nsm_lt=co__action&nsm_lv=Bogus")
        self.assertEqual(ctx["nsm_active_link_value"], "")
        active = next(g for g in ctx["nsm_link_type_groups"] if g["is_active"])
        self.assertEqual(len(active["page"]), 3)

    def test_pagination_limits_page_objects(self):
        request = self.factory.get("/x/?nsm_lt=co__action")
        many = [
            _obj(f"a-{i:04d}", "Permit", "Permit")
            for i in range(DEFAULT_PER_PAGE + 20)
        ]
        groups = [_group("co__action", "Action", many)]
        ctx = prepare_link_tab_view(groups, request)
        active = ctx["nsm_link_type_groups"][0]
        self.assertEqual(len(active["page"]), DEFAULT_PER_PAGE)
        self.assertEqual(active["pagination"]["total"], DEFAULT_PER_PAGE + 20)
        self.assertTrue(active["pagination"]["next_url"])
        self.assertEqual(active["pagination"]["num_pages"], 2)

    def test_second_page_returns_remaining(self):
        request = self.factory.get("/x/?nsm_lt=co__action&nsm_lp=2")
        many = [
            _obj(f"a-{i:04d}", "Permit", "Permit")
            for i in range(DEFAULT_PER_PAGE + 20)
        ]
        groups = [_group("co__action", "Action", many)]
        ctx = prepare_link_tab_view(groups, request)
        active = ctx["nsm_link_type_groups"][0]
        self.assertEqual(len(active["page"]), 20)
        self.assertTrue(active["pagination"]["prev_url"])

    def test_sort_by_name_descending(self):
        request = self.factory.get("/x/?nsm_lt=co__action&nsm_lo=-name")
        groups = [
            _group(
                "co__action",
                "Action",
                [_obj("alpha"), _obj("beta"), _obj("gamma")],
            )
        ]
        ctx = prepare_link_tab_view(groups, request)
        names = [o["name"] for o in ctx["nsm_link_type_groups"][0]["page"]]
        self.assertEqual(names, ["gamma", "beta", "alpha"])

    def test_empty_groups_returns_safe_context(self):
        ctx = prepare_link_tab_view([], self.factory.get("/x/"))
        self.assertEqual(ctx["nsm_link_type_groups"], [])
        self.assertEqual(ctx["nsm_active_link_type"], "")


class LinkTabTemplateTests(SimpleTestCase):
    def _render(self, ctx):
        base = {
            "nsm_panel_label": "Security",
            "nsm_security_badge": None,
            "nsm_analyzer_url": "/analyzer/",
            "nsm_assign_url": "/assign/",
            "nsm_page_addr_analyzable": False,
            "nsm_rulebook_groups": [],
            "nsm_enforcement_point": None,
        }
        base.update(ctx)
        return render_to_string("netbox_nsm/inc/security_links.html", base)

    def test_renders_type_tabs_and_value_pills(self):
        request = RequestFactory().get("/dcim/devices/1/security/")
        groups = [
            _group(
                "co__action",
                "Action",
                [
                    _obj("act-permit", "Permit", "Permit"),
                    _obj("act-deny", "Deny", "Deny"),
                ],
                show_actions=True,
            ),
            _group("ipam__prefix", "Prefix", [_obj("10.0.0.0/8")]),
        ]
        ctx = prepare_link_tab_view(groups, request)
        html = self._render(ctx)
        self.assertIn("nsm-link-tabs", html)
        self.assertIn("Action", html)
        self.assertIn("Prefix", html)
        # Value sub-filter pills for the active "Action" tab.
        self.assertIn('class="nsm-link-value-filter', html)
        self.assertIn("Permit", html)
        self.assertIn("Deny", html)
        # Active tab renders rows; the non-active "Prefix" pane is not emitted.
        self.assertIn('id="nsm-ltab-co__action"', html)
        self.assertNotIn('id="nsm-ltab-ipam__prefix"', html)

    def test_value_filter_hidden_without_grouping(self):
        request = RequestFactory().get("/x/")
        groups = [
            _group("ipam__prefix", "Prefix", [_obj("10.0.0.0/8"), _obj("10.1.0.0/16")])
        ]
        ctx = prepare_link_tab_view(groups, request)
        html = self._render(ctx)
        self.assertNotIn('class="nsm-link-value-filter', html)

    def test_pagination_controls_rendered(self):
        request = RequestFactory().get("/x/?nsm_lt=co__action&nsm_pp=25")
        many = [_obj(f"a-{i:04d}", "Permit", "Permit") for i in range(60)]
        groups = [_group("co__action", "Action", many)]
        ctx = prepare_link_tab_view(groups, request)
        html = self._render(ctx)
        self.assertIn("nsm-link-paginator", html)
        self.assertIn("Per Page", html)
        self.assertIn("page-link", html)
