"""Tests for Security tab flat linked-objects table."""

from __future__ import annotations

from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.security.tab.links import (
    DEFAULT_PER_PAGE,
    PARAM_Q,
    PARAM_ROW_TYPE,
    build_row_type_options,
    flatten_link_type_groups,
    prepare_link_tab_view,
)
from netbox_nsm.security.tab.value_groups import (
    UNGROUPED_KEY,
    UNGROUPED_LABEL,
    nsm_object_group_value,
)


def _obj(name, value_key="_none", value_label="—", **extra):
    row = {
        "name": name,
        "url": f"/o/{name}/",
        "value_key": value_key,
        "value_label": value_label,
    }
    row.update(extra)
    return row


def _group(type_key, label, objects, **extra):
    base = {
        "type_key": type_key,
        "type_label": label,
        "count": len(objects),
        "objects": objects,
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


class FlattenLinkTypeGroupsTests(SimpleTestCase):
    def test_stamps_former_tab_name_as_type_column(self):
        rows = flatten_link_type_groups(
            [
                _group("co__zone", "Zones", [_obj("trust")]),
                _group("co__rule", "Rules", [_obj("rule-1")]),
            ]
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["row_type_label"], "Zones")
        self.assertEqual(rows[0]["row_type_filter_key"], "co__zone")
        self.assertEqual(rows[1]["row_type_label"], "Rules")


class BuildRowTypeOptionsTests(SimpleTestCase):
    def test_collects_distinct_type_labels(self):
        rows = flatten_link_type_groups(
            [
                _group("co__zone", "Zones", [_obj("a"), _obj("b")]),
                _group("co__rule", "Rules", [_obj("c")]),
            ]
        )
        options = build_row_type_options(rows)
        self.assertEqual(
            [(opt["label"], opt["count"]) for opt in options],
            [("Rules", 1), ("Zones", 2)],
        )


class PrepareLinkTabViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _groups(self):
        return [
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

    def test_flattens_all_groups_into_one_table(self):
        ctx = prepare_link_tab_view(self._groups(), self.factory.get("/security/"))
        table = ctx["nsm_link_table"]
        self.assertIsNotNone(table)
        self.assertEqual(ctx["nsm_link_count"], 4)
        self.assertEqual(len(table["page"]), 4)
        labels = {row["row_type_label"] for row in table["page"]}
        self.assertEqual(labels, {"Action", "Prefix"})

    def test_quicksearch_filters_rows(self):
        request = self.factory.get(f"/security/?{PARAM_Q}=deny")
        ctx = prepare_link_tab_view(self._groups(), request)
        page = ctx["nsm_link_table"]["page"]
        self.assertEqual(len(page), 1)
        self.assertEqual(page[0]["name"], "act-deny-1")

    def test_type_filter_restricts_rows(self):
        request = self.factory.get(f"/security/?{PARAM_ROW_TYPE}=ipam__prefix")
        ctx = prepare_link_tab_view(self._groups(), request)
        page = ctx["nsm_link_table"]["page"]
        self.assertEqual(len(page), 1)
        self.assertEqual(page[0]["row_type_label"], "Prefix")

    def test_pagination_limits_page_objects(self):
        request = self.factory.get("/security/")
        many = [_obj(f"a-{i:04d}", "Permit", "Permit") for i in range(DEFAULT_PER_PAGE + 20)]
        groups = [_group("co__action", "Action", many)]
        table = prepare_link_tab_view(groups, request)["nsm_link_table"]
        self.assertEqual(len(table["page"]), DEFAULT_PER_PAGE)
        self.assertEqual(table["pagination"]["total"], DEFAULT_PER_PAGE + 20)

    def test_sort_by_name_descending(self):
        request = self.factory.get("/security/?nsm_lo=-name")
        groups = [
            _group("co__action", "Action", [_obj("alpha"), _obj("beta"), _obj("gamma")])
        ]
        page = prepare_link_tab_view(groups, request)["nsm_link_table"]["page"]
        self.assertEqual([o["name"] for o in page], ["gamma", "beta", "alpha"])

    def test_empty_groups_return_no_table(self):
        ctx = prepare_link_tab_view([], self.factory.get("/security/"))
        self.assertIsNone(ctx["nsm_link_table"])
        self.assertEqual(ctx["nsm_link_count"], 0)


class SecurityLinkObjectsTemplateTests(SimpleTestCase):
    def _render(self, ctx):
        return render_to_string(
            "netbox_nsm/inc/security_link_objects.html",
            ctx,
        )

    def test_renders_quicksearch_and_type_filter_without_tabs_or_pills(self):
        groups = [
            _group("co__zone", "Zones", [_obj("trust")]),
            _group("co__rule", "Rules", [_obj("rule-1")]),
        ]
        ctx = prepare_link_tab_view(groups, RequestFactory().get("/security/"))
        html = self._render(ctx)
        self.assertIn("nsm-link-controls", html)
        self.assertIn('placeholder="Quick search"', html)
        self.assertIn("All types", html)
        self.assertIn("Zones", html)
        self.assertIn("Rules", html)
        self.assertNotIn('class="nav nav-tabs nsm-link-tabs"', html)
        self.assertNotIn('class="nsm-link-value-filter', html)
        self.assertNotIn("nsm-link-value-badge", html)

    def test_renders_type_column_from_former_tab_names(self):
        groups = [_group("co__zone", "Zones", [_obj("trust")])]
        ctx = prepare_link_tab_view(groups, RequestFactory().get("/security/"))
        html = self._render(ctx)
        self.assertIn('class="col-type"', html)
        self.assertIn("Zones", html)
