"""Rules tab layout helpers."""

from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory

from netbox_nsm.models import (
    Rule,
    Rulebook,
    RulebookField,
    RulebookFieldKind,
    RulebookFieldType,
    TypeConfig,
)
from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields
from netbox_nsm.rulebook_rules_tab import (
    RULES_HTML_ROW_LIMIT,
    _annotate_rules_columns,
    _attach_rules_cells,
    _rules_column_width_fields,
    _rules_filter_needs_full_scan,
    _render_status_cell_html,
    build_rulebook_rules_tab_context,
    build_rules_page_url,
    build_rules_sort_url,
    build_rules_sort_url_for_order,
    flatten_rules_column_defs,
    parse_rules_filter_model,
    rules_object_column_display_label,
)
from utilities.paginator import EnhancedPaginator
from netbox_nsm.views import rulebook as rulebook_views
from utilities.testing import TestCase


class RulebookRulesLayoutTests(TestCase):
    def test_flatten_column_defs_matches_ag_grid_structure(self):
        column_defs = [
            {"colId": "status", "headerName": "Status", "minWidth": 88},
            {"colId": "name", "headerName": "Name", "minWidth": 160},
            {
                "headerName": "SOURCE",
                "children": [
                    {"field": "source::ct_1", "headerName": "Zones", "minWidth": 220},
                    {"field": "source::ct_2", "headerName": "Addresses", "width": 180},
                ],
            },
            {"colId": "_actions", "headerName": "", "width": 72},
        ]
        flat = flatten_rules_column_defs(column_defs)
        self.assertEqual(len(flat), 5)
        self.assertEqual(flat[0]["slug"], "status")
        self.assertEqual(flat[0]["col_id"], "status")
        self.assertEqual(flat[0]["default_width_px"], 88)
        self.assertEqual(flat[0]["min_width_px"], 29)
        self.assertEqual(flat[1]["default_width_px"], 160)
        self.assertEqual(flat[1]["min_width_px"], 53)
        self.assertEqual(flat[2]["key"], "source::ct_1")
        self.assertEqual(flat[2]["col_id"], "source::ct_1")
        self.assertEqual(flat[2]["group_header"], "SOURCE")
        self.assertEqual(flat[2]["label"], "Zones (SOURCE)")
        self.assertEqual(flat[3]["label"], "Addresses (SOURCE)")
        self.assertEqual(flat[2]["default_width_px"], 220)
        self.assertEqual(flat[2]["min_width_px"], 73)
        self.assertEqual(flat[3]["default_width_px"], 180)
        self.assertEqual(flat[3]["min_width_px"], 60)
        self.assertEqual(flat[4]["kind"], "actions")
        self.assertEqual(flat[4]["default_width_px"], 72)
        self.assertEqual(flat[4]["min_width_px"], 24)

    def test_sort_urls_include_explicit_asc_and_desc(self):
        request = RequestFactory().get("/rules/?cell_mode=inline")
        flat = [
            {
                "kind": "system",
                "slug": "name",
                "col_id": "name",
                "key": "name",
            }
        ]
        _annotate_rules_columns(
            flat,
            request=request,
            sort_field="index",
            sort_order="asc",
            base_qs_str="cell_mode=inline",
        )
        meta = flat[0]
        self.assertIn("sort=name&order=asc", meta["sort_url_asc"])
        self.assertIn("sort=name&order=desc", meta["sort_url_desc"])
        self.assertIn("cell_mode=inline", meta["sort_url_asc"])
        self.assertEqual(
            build_rules_sort_url(
                request,
                "name",
                current_sort="index",
                current_order="asc",
                base_qs_str="cell_mode=inline",
            ),
            build_rules_sort_url_for_order(
                request, "name", "asc", base_qs_str="cell_mode=inline"
            ),
        )
        self.assertIn(
            "order=desc",
            build_rules_sort_url(
                request,
                "name",
                current_sort="name",
                current_order="asc",
                base_qs_str="cell_mode=inline",
            ),
        )

    def test_sort_urls_omit_existing_sort_query_params(self):
        request = RequestFactory().get("/rules/?sort=index&order=asc&cell_mode=inline")
        flat = [
            {
                "kind": "system",
                "slug": "name",
                "col_id": "name",
                "key": "name",
            }
        ]
        get_params = request.GET.copy()
        get_params.pop("page", None)
        get_params.pop("sort", None)
        get_params.pop("order", None)
        base_qs_str = get_params.urlencode()
        _annotate_rules_columns(
            flat,
            request=request,
            sort_field="index",
            sort_order="asc",
            base_qs_str=base_qs_str,
        )
        sort_url = flat[0]["sort_url"]
        self.assertEqual(sort_url.count("sort="), 1)
        self.assertEqual(sort_url.count("order="), 1)
        self.assertIn("cell_mode=inline", sort_url)
        self.assertIn("sort=name&order=asc", sort_url)

    def test_rules_column_width_fields_use_third_of_default_as_min(self):
        meta = _rules_column_width_fields({"width": 108, "minWidth": 88})
        self.assertEqual(
            meta,
            {
                "default_width_px": 108,
                "min_width_px": 36,
                "width_px": 108,
            },
        )

    def test_status_cell_uses_netbox_object_list_badge_markup(self):
        html = _render_status_cell_html(True)
        self.assertIn('class="badge text-bg-blue"', html)
        self.assertNotIn("rounded-pill", html)

        off_html = _render_status_cell_html(False)
        self.assertIn('class="badge text-bg-secondary"', off_html)

    def test_object_cells_render_all_items_without_js_expand(self):
        column_defs = [
            {"colId": "name", "headerName": "Name"},
            {
                "headerName": "SOURCE",
                "children": [{"field": "source::ct_1", "headerName": "Zones"}],
            },
            {"colId": "_actions", "headerName": ""},
        ]
        flat = flatten_rules_column_defs(column_defs)
        rows = [
            {
                "name": "r1",
                "system": {"name": "r1", "url": "/rules/1/"},
                "cells_items": {
                    "source::ct_1": [
                        {"name": "DMZ", "url": "/z/1/", "color": "#336699"},
                        {"name": "LAN", "url": "/z/2/", "color": "#112233"},
                        {"name": "WAN", "url": "/z/3/", "color": "#445566"},
                    ]
                },
                "edit_url": "/edit/",
                "delete_url": "/delete/",
            }
        ]

        class _Req:
            COOKIES = {}

            user = type("U", (), {"has_perm": lambda self, p: True})()

        _attach_rules_cells(
            rows,
            flat,
            request=_Req(),
            can_change=True,
            can_delete=True,
            object_fields_by_slug={},
        )
        object_html = rows[0]["rules_cells"][1]["html"]
        self.assertIn("data-nsm-filter-value", object_html)
        self.assertIn("DMZ", object_html)
        self.assertIn("LAN", object_html)
        self.assertIn("WAN", object_html)
        self.assertNotIn("onclick", object_html)
        self.assertNotIn("nsm-ag-cell-more", object_html)
        self.assertIn("btn-group btn-group-sm", rows[0]["rules_cells"][2]["html"])


class RulebookRulesContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="Rules Context RB",
            rulebook_type="security_rules",
        )
        ensure_system_rulebook_fields(cls.rulebook)
        cls.type_config, _ = TypeConfig.objects.get_or_create(
            content_type=ContentType.objects.order_by("pk").first(),
            defaults={"name": "Rules Type"},
        )
        cls.object_field = RulebookField.objects.create(
            rulebook=cls.rulebook,
            slug="source",
            name="Source",
            placement="source",
            field_kind=RulebookFieldKind.OBJECT,
            visible=True,
            sort_order=50,
        )
        RulebookFieldType.objects.create(
            field=cls.object_field,
            type_config=cls.type_config,
            visible=True,
        )
        Rule.objects.create(
            rulebook=cls.rulebook,
            name="ctx-rule",
            index=5,
            enabled=True,
        )

    def test_build_context_columns_follow_rulebook_field_layout(self):
        request = RequestFactory().get("/")
        request.user = self.user
        ctx = build_rulebook_rules_tab_context(
            request,
            self.rulebook,
            view_helpers=rulebook_views,
        )
        flat = ctx["rules_flat_columns"]
        slugs = [col.get("slug") for col in flat if col.get("kind") == "system"]
        self.assertEqual(slugs, ["index", "status", "name", "description"])
        object_cols = [col for col in flat if col.get("kind") == "object"]
        self.assertEqual(len(object_cols), 1)
        self.assertTrue(object_cols[0]["key"].startswith("source::"))
        self.assertTrue(ctx["rules_has_object_groups"])
        self.assertFalse(ctx["rules_has_object_header_stack"])
        source_def = next(
            col for col in ctx["rules_column_defs"] if col.get("children")
        )
        self.assertEqual(source_def.get("headerName"), "Source")
        child = source_def["children"][0]
        self.assertEqual(
            child["display_label"],
            rules_object_column_display_label(
                child.get("headerName") or "",
                source_def.get("headerName") or "",
            ),
        )

    def test_build_context_column_widths_match_defaults(self):
        request = RequestFactory().get("/")
        request.user = self.user
        ctx = build_rulebook_rules_tab_context(
            request,
            self.rulebook,
            view_helpers=rulebook_views,
        )
        status_col = next(
            col for col in ctx["rules_flat_columns"] if col.get("slug") == "status"
        )
        self.assertEqual(status_col["default_width_px"], 108)
        self.assertEqual(status_col["min_width_px"], 36)
        object_col = next(
            col for col in ctx["rules_flat_columns"] if col.get("kind") == "object"
        )
        self.assertEqual(object_col["default_width_px"], 260)
        self.assertEqual(object_col["min_width_px"], 86)
        actions_col = next(
            col for col in ctx["rules_flat_columns"] if col.get("kind") == "actions"
        )
        self.assertEqual(actions_col["default_width_px"], 72)
        self.assertEqual(actions_col["min_width_px"], 24)
        actions_def = next(
            col for col in ctx["rules_column_defs"] if col.get("colId") == "_actions"
        )
        self.assertEqual(actions_def["rules_meta"]["default_width_px"], 72)
        self.assertEqual(actions_def["rules_meta"]["min_width_px"], 24)

    def test_build_context_exposes_filter_column_map_for_cell_drag(self):
        request = RequestFactory().get("/")
        request.user = self.user
        ctx = build_rulebook_rules_tab_context(
            request,
            self.rulebook,
            view_helpers=rulebook_views,
        )
        cfg = ctx["rules_chrome_config"]
        self.assertIn("filterColumnMap", cfg)
        self.assertIn("filterColumnShorthand", cfg)
        self.assertEqual(cfg["filterColumnMap"]["name"], "Name")
        self.assertEqual(cfg["filterColumnMap"]["status"], "Status")
        object_col = next(
            col for col in ctx["rules_flat_columns"] if col.get("kind") == "object"
        )
        self.assertIn(object_col["col_id"], cfg["filterColumnMap"])

    def test_hiding_object_field_removes_object_columns(self):
        self.object_field.visible = False
        self.object_field.save(update_fields=["visible"])
        request = RequestFactory().get("/")
        request.user = self.user
        ctx = build_rulebook_rules_tab_context(
            request,
            self.rulebook,
            view_helpers=rulebook_views,
        )
        object_cols = [col for col in ctx["rules_flat_columns"] if col.get("kind") == "object"]
        self.assertEqual(object_cols, [])
        self.assertFalse(ctx["rules_has_object_groups"])

    def test_build_context_paginates_rules(self):
        Rule.objects.bulk_create(
            [
                Rule(
                    rulebook=self.rulebook,
                    name=f"page-rule-{idx}",
                    index=idx,
                    enabled=True,
                )
                for idx in range(RULES_HTML_ROW_LIMIT + 3)
            ]
        )
        request = RequestFactory().get("/?per_page=25")
        request.user = self.user
        ctx = build_rulebook_rules_tab_context(
            request,
            self.rulebook,
            view_helpers=rulebook_views,
        )
        total = RULES_HTML_ROW_LIMIT + 4
        self.assertEqual(ctx["rules_total_rules"], total)
        self.assertEqual(ctx["rules_page_obj"].number, 1)
        # EnhancedPaginator orphans=5 merges a short trailing page into the previous one.
        self.assertEqual(len(ctx["rules_rows"]), total)
        self.assertEqual(ctx["rules_paginator"].num_pages, 1)
        self.assertFalse(ctx["rules_page_obj"].has_next())
        self.assertFalse(ctx["rules_page_obj"].has_previous())

        Rule.objects.bulk_create(
            [
                Rule(
                    rulebook=self.rulebook,
                    name=f"page-rule-extra-{idx}",
                    index=1000 + idx,
                    enabled=True,
                )
                for idx in range(10)
            ]
        )
        request_page2 = RequestFactory().get("/?page=2&per_page=25")
        request_page2.user = self.user
        ctx_page2 = build_rulebook_rules_tab_context(
            request_page2,
            self.rulebook,
            view_helpers=rulebook_views,
        )
        self.assertEqual(ctx_page2["rules_total_rules"], total + 10)
        self.assertEqual(ctx_page2["rules_paginator"].num_pages, 2)
        self.assertEqual(ctx_page2["rules_page_obj"].number, 2)
        self.assertFalse(ctx_page2["rules_page_obj"].has_next())

    def test_invalid_page_clamps_to_last_page(self):
        Rule.objects.bulk_create(
            [
                Rule(
                    rulebook=self.rulebook,
                    name=f"clamp-rule-{idx}",
                    index=idx,
                    enabled=True,
                )
                for idx in range(RULES_HTML_ROW_LIMIT + 1)
            ]
        )
        request = RequestFactory().get("/?page=999&per_page=25")
        request.user = self.user
        ctx = build_rulebook_rules_tab_context(
            request,
            self.rulebook,
            view_helpers=rulebook_views,
        )
        self.assertEqual(ctx["rules_page_obj"].number, 1)
        self.assertEqual(len(ctx["rules_rows"]), RULES_HTML_ROW_LIMIT + 2)

    def test_page_url_preserves_other_query_params(self):
        request = RequestFactory().get("/rulebooks/1/rules/?foo=bar&page=3")
        request.user = self.user
        url = build_rules_page_url(request, 2, "foo=bar")
        self.assertIn("page=2", url)
        self.assertIn("foo=bar", url)

    def test_smart_pages_include_ellipsis_for_large_page_counts(self):
        paginator = EnhancedPaginator(range(500), 25)
        page = paginator.get_page(10)
        self.assertEqual(page.smart_pages(), [1, False, 8, 9, 10, 11, 12, False, 20])

    def test_name_filter_narrows_rows(self):
        Rule.objects.create(
            rulebook=self.rulebook,
            name="alpha-only",
            index=99,
            enabled=True,
        )
        request = RequestFactory().get("/?f_name=alpha")
        request.user = self.user
        ctx = build_rulebook_rules_tab_context(
            request,
            self.rulebook,
            view_helpers=rulebook_views,
        )
        names = [
            row.get("name") or (row.get("system") or {}).get("name")
            for row in ctx["rules_rows"]
        ]
        self.assertEqual(names, ["alpha-only"])
        self.assertTrue(ctx["rules_filter_active"])

    def test_name_filter_and_requires_all_terms(self):
        Rule.objects.bulk_create(
            [
                Rule(
                    rulebook=self.rulebook,
                    name="rule1-only",
                    index=10,
                    enabled=True,
                ),
                Rule(
                    rulebook=self.rulebook,
                    name="rule2-only",
                    index=11,
                    enabled=True,
                ),
                Rule(
                    rulebook=self.rulebook,
                    name="rule1-and-rule2",
                    index=12,
                    enabled=True,
                ),
            ]
        )
        request = RequestFactory().get("/?f_name=rule1 AND rule2")
        request.user = self.user
        ctx = build_rulebook_rules_tab_context(
            request,
            self.rulebook,
            view_helpers=rulebook_views,
        )
        names = {
            row.get("name") or (row.get("system") or {}).get("name")
            for row in ctx["rules_rows"]
        }
        self.assertEqual(names, {"rule1-and-rule2"})

    def test_name_filter_or_matches_any_term(self):
        Rule.objects.bulk_create(
            [
                Rule(
                    rulebook=self.rulebook,
                    name="rule1-only",
                    index=20,
                    enabled=True,
                ),
                Rule(
                    rulebook=self.rulebook,
                    name="rule2-only",
                    index=21,
                    enabled=True,
                ),
                Rule(
                    rulebook=self.rulebook,
                    name="other-name",
                    index=22,
                    enabled=True,
                ),
            ]
        )
        request = RequestFactory().get("/?f_name=rule1 OR rule2")
        request.user = self.user
        ctx = build_rulebook_rules_tab_context(
            request,
            self.rulebook,
            view_helpers=rulebook_views,
        )
        names = {
            row.get("name") or (row.get("system") or {}).get("name")
            for row in ctx["rules_rows"]
        }
        self.assertEqual(names, {"rule1-only", "rule2-only"})

    def test_parse_rules_filter_model_simple_contains_unchanged(self):
        request = RequestFactory().get("/?f_name=alpha")
        flat = [{"kind": "system", "slug": "name", "col_id": "name"}]
        model = parse_rules_filter_model(request, flat)
        self.assertEqual(
            model,
            {"name": {"filterType": "text", "type": "contains", "filter": "alpha"}},
        )

    def test_parse_rules_filter_model_parses_and_or(self):
        request = RequestFactory().get("/?f_name=rule1 AND rule2")
        flat = [{"kind": "system", "slug": "name", "col_id": "name"}]
        model = parse_rules_filter_model(request, flat)
        self.assertEqual(model["name"]["operator"], "AND")
        self.assertEqual(
            [cond["filter"] for cond in model["name"]["conditions"]],
            ["rule1", "rule2"],
        )

        request_or = RequestFactory().get("/?f_name=rule1 OR rule2")
        model_or = parse_rules_filter_model(request_or, flat)
        self.assertEqual(model_or["name"]["operator"], "OR")
        self.assertEqual(
            [cond["filter"] for cond in model_or["name"]["conditions"]],
            ["rule1", "rule2"],
        )

    def test_status_filter_narrows_rows(self):
        Rule.objects.bulk_create(
            [
                Rule(
                    rulebook=self.rulebook,
                    name="enabled-rule",
                    index=1,
                    enabled=True,
                ),
                Rule(
                    rulebook=self.rulebook,
                    name="disabled-rule",
                    index=2,
                    enabled=False,
                ),
            ]
        )
        request = RequestFactory().get("/?f_status=on")
        request.user = self.user
        ctx = build_rulebook_rules_tab_context(
            request,
            self.rulebook,
            view_helpers=rulebook_views,
        )
        names = [
            row.get("name") or (row.get("system") or {}).get("name")
            for row in ctx["rules_rows"]
        ]
        self.assertEqual(set(names), {"ctx-rule", "enabled-rule"})
        self.assertTrue(ctx["rules_filter_active"])

    def test_filter_q_populates_column_quick_search_values(self):
        request = RequestFactory().get("/?filter_q=Name(ctx-rule)")
        request.user = self.user
        ctx = build_rulebook_rules_tab_context(
            request,
            self.rulebook,
            view_helpers=rulebook_views,
        )
        name_col = next(
            col for col in ctx["rules_flat_columns"] if col.get("slug") == "name"
        )
        self.assertEqual(name_col["filter_value"], "ctx-rule")
        self.assertTrue(ctx["rules_filter_active"])

    def test_column_filter_takes_precedence_over_filter_q(self):
        Rule.objects.bulk_create(
            [
                Rule(
                    rulebook=self.rulebook,
                    name="enabled-rule",
                    index=1,
                    enabled=True,
                ),
                Rule(
                    rulebook=self.rulebook,
                    name="disabled-rule",
                    index=2,
                    enabled=False,
                ),
            ]
        )
        request = RequestFactory().get(
            "/?filter_q=Name(disabled-rule)&f_status=on"
        )
        request.user = self.user
        ctx = build_rulebook_rules_tab_context(
            request,
            self.rulebook,
            view_helpers=rulebook_views,
        )
        names = [
            row.get("name") or (row.get("system") or {}).get("name")
            for row in ctx["rules_rows"]
        ]
        self.assertEqual(set(names), {"ctx-rule", "enabled-rule"})

    def test_sort_by_name_desc(self):
        Rule.objects.bulk_create(
            [
                Rule(rulebook=self.rulebook, name="aaa", index=1, enabled=True),
                Rule(rulebook=self.rulebook, name="zzz", index=2, enabled=True),
            ]
        )
        request = RequestFactory().get("/?sort=name&order=desc")
        request.user = self.user
        ctx = build_rulebook_rules_tab_context(
            request,
            self.rulebook,
            view_helpers=rulebook_views,
        )
        names = [
            (row.get("system") or {}).get("name") or row.get("name")
            for row in ctx["rules_rows"]
        ]
        self.assertEqual(names[0], "zzz")

    def test_db_pagination_returns_only_one_page_of_rows(self):
        Rule.objects.bulk_create(
            [
                Rule(
                    rulebook=self.rulebook,
                    name=f"bulk-{idx}",
                    index=idx,
                    enabled=True,
                )
                for idx in range(RULES_HTML_ROW_LIMIT + 10)
            ]
        )
        request = RequestFactory().get("/?per_page=25")
        request.user = self.user
        ctx = build_rulebook_rules_tab_context(
            request,
            self.rulebook,
            view_helpers=rulebook_views,
        )
        self.assertEqual(len(ctx["rules_rows"]), RULES_HTML_ROW_LIMIT)
        self.assertEqual(
            ctx["rules_total_rules"],
            RULES_HTML_ROW_LIMIT + 11,
        )

    def test_object_column_filter_requires_full_scan(self):
        flat = [{"kind": "object", "key": "source::ct_1", "slug": "", "label": "Zones"}]
        self.assertTrue(
            _rules_filter_needs_full_scan(
                {"source::ct_1": {"filter": "dmz"}},
                "index",
            )
        )
        self.assertFalse(_rules_filter_needs_full_scan({"name": {"filter": "x"}}, "index"))
