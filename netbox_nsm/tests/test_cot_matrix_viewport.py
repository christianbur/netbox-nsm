"""Matrix tab viewport payload and sparse cell map."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.rulebooks.matrix.cot_matrix_tab_context import (
    build_cot_matrix_tab_context,
    build_sparse_matrix_cells,
    serialize_matrix_zone_axis,
)
from netbox_nsm.rulebooks.matrix.matrix_utils import (
    MATRIX_VIEWPORT_COL_BUFFER,
    MATRIX_VIEWPORT_DEFAULT_COLS,
    MATRIX_VIEWPORT_DEFAULT_ROWS,
    MATRIX_VIEWPORT_ROW_BUFFER,
)


class SerializeMatrixZoneAxisTests(SimpleTestCase):
    def test_preserves_zone_order_for_destination_axis(self):
        zones = [
            SimpleNamespace(pk=3, get_absolute_url=lambda: "/zones/3/"),
            SimpleNamespace(pk=1, get_absolute_url=lambda: "/zones/1/"),
            SimpleNamespace(pk=2, get_absolute_url=lambda: "/zones/2/"),
        ]
        rows = serialize_matrix_zone_axis(
            zones,
            zone_labels={3: "zone_c", 1: "zone_a", 2: "zone_b"},
            zone_label_display={3: "C", 1: "A", 2: "B"},
            request=RequestFactory().get("/"),
        )
        self.assertEqual([row["pk"] for row in rows], [3, 1, 2])
        self.assertEqual([row["label_display"] for row in rows], ["C", "A", "B"])

    def test_serializes_zone_labels_and_urls(self):
        zone = SimpleNamespace(pk=7, get_absolute_url=lambda: "/zones/7/")
        rows = serialize_matrix_zone_axis(
            [zone],
            zone_labels={7: "Trust Zone"},
            zone_label_display={7: "Trust"},
            request=RequestFactory().get("/"),
        )
        self.assertEqual(rows[0]["pk"], 7)
        self.assertEqual(rows[0]["label"], "Trust Zone")
        self.assertEqual(rows[0]["label_display"], "Trust")
        self.assertEqual(rows[0]["url"], "/zones/7/")


class BuildSparseMatrixCellsTests(SimpleTestCase):
    def test_omits_empty_non_self_cells(self):
        src = SimpleNamespace(pk=1)
        dst = SimpleNamespace(pk=2)
        cells = build_sparse_matrix_cells(
            [src],
            [dst],
            {},
            src_field="source_zones",
            dst_field="destination_zones",
            zone_labels={1: "A", 2: "B"},
            rules_url_base="/rules/",
            request=RequestFactory().get("/"),
        )
        self.assertEqual(cells, {})

    def test_includes_self_diagonal_without_rules(self):
        zone = SimpleNamespace(pk=3)
        cells = build_sparse_matrix_cells(
            [zone],
            [zone],
            {},
            src_field="source_zones",
            dst_field="destination_zones",
            zone_labels={3: "Loop"},
            rules_url_base="/rules/",
            request=RequestFactory().get("/"),
        )
        self.assertIn("3:3", cells)
        self.assertTrue(cells["3:3"]["is_self"])
        self.assertEqual(cells["3:3"]["fwd"]["count"], 0)

    @patch("netbox_nsm.rulebooks.matrix.cot_matrix_tab_context.build_matrix_cell_rules_filter_url")
    def test_includes_populated_cells_with_filter_href(self, mock_filter_url):
        mock_filter_url.return_value = "/rules/?filtered=1"
        src = SimpleNamespace(pk=1)
        dst = SimpleNamespace(pk=2)
        rule = SimpleNamespace(_color="#ff0000", _action_label="Allow")
        cells = build_sparse_matrix_cells(
            [src],
            [dst],
            {(1, 2): [rule]},
            src_field="source_zones",
            dst_field="destination_zones",
            zone_labels={1: "A", 2: "B"},
            rules_url_base="/rules/",
            request=RequestFactory().get("/"),
        )
        self.assertEqual(cells["1:2"]["fwd"]["count"], 1)
        self.assertEqual(cells["1:2"]["filter_href"], "/rules/?filtered=1")


class CotMatrixViewportContextTests(SimpleTestCase):
    @patch("netbox_nsm.rulebooks.matrix.cot_matrix_tab_context.build_sparse_matrix_cells")
    @patch("netbox_nsm.rulebooks.matrix.cot_matrix_tab_context.serialize_matrix_zone_axis")
    @patch("netbox_nsm.rulebooks.matrix.cot_matrix_tab_context._action_legend")
    @patch("netbox_nsm.rulebooks.matrix.cot_matrix_tab_context.resolve_matrix_object_type_selection")
    @patch("netbox_nsm.rulebooks.matrix.cot_matrix_tab_context.dedupe_matrix_object_types")
    @patch("netbox_nsm.rulebooks.matrix.cot_matrix_tab_context._matrix_available_types")
    @patch("netbox_nsm.rulebooks.matrix.cot_matrix_tab_context.prefetch_cot_multiobject_fields")
    @patch("netbox_nsm.rulebooks.matrix.cot_matrix_tab_context.cot_rule_instances_queryset")
    @patch("netbox_nsm.rulebooks.matrix.cot_matrix_tab_context.cot_rulebook_matrix_enabled")
    def test_build_returns_matrix_viewport_not_full_rows(
        self,
        mock_enabled,
        mock_qs_fn,
        mock_prefetch,
        mock_available_types,
        mock_dedupe,
        mock_resolve_ct,
        mock_legend,
        mock_serialize_axis,
        mock_sparse_cells,
    ):
        mock_enabled.return_value = True
        rule = SimpleNamespace(pk=1)
        qs = MagicMock()
        qs.order_by.return_value = [rule]
        mock_qs_fn.return_value = qs
        mock_available_types.return_value = [{"ct_id": 7, "label": "Zones"}]
        mock_dedupe.return_value = [{"ct_id": 7, "label": "Zones"}]
        mock_resolve_ct.return_value = 7
        mock_legend.return_value = []
        mock_serialize_axis.return_value = [{"pk": 1, "label": "A", "label_display": "A", "url": "/a/"}]
        mock_sparse_cells.return_value = {"1:2": {"fwd": {"count": 1}}}

        fields = MagicMock()
        fields.values_list.return_value = ["source_zones", "destination_zones"]
        cot = SimpleNamespace(slug="nsm_rb_demo_zone_matrix", fields=fields)
        virtual_rb = SimpleNamespace(cot=cot, slug="nsm_rb_demo_zone_matrix")
        request = RequestFactory().get("/matrix/")

        with (
            patch(
                "netbox_nsm.rulebooks.matrix.cot_matrix_tab_context.get_display_template_map",
                return_value={},
            ),
            patch(
                "netbox_nsm.rulebooks.matrix.cot_matrix_tab_context.reverse",
                return_value="/rules/",
            ),
            patch(
                "netbox_nsm.rulebooks.matrix.cot_matrix_tab_context.with_branch_query",
                side_effect=lambda url, _req: url,
            ),
            patch(
                "netbox_nsm.rulebooks.matrix.cot_matrix_tab_context.ContentType"
            ) as mock_ct,
        ):
            mock_ct.DoesNotExist = Exception
            mock_ct.objects.get.side_effect = lambda pk: SimpleNamespace(
                pk=pk,
                model_class=lambda: None,
            )
            ctx = build_cot_matrix_tab_context(request, virtual_rb)

        self.assertIn("matrix_viewport", ctx)
        self.assertNotIn("matrix_rows", ctx)
        viewport = ctx["matrix_viewport"]
        self.assertIn("cells", viewport)
        self.assertIn("src_zones", viewport)
        self.assertEqual(viewport["default_rows"], MATRIX_VIEWPORT_DEFAULT_ROWS)
        self.assertEqual(viewport["default_cols"], MATRIX_VIEWPORT_DEFAULT_COLS)
        self.assertEqual(viewport["row_buffer"], MATRIX_VIEWPORT_ROW_BUFFER)
        self.assertEqual(viewport["col_buffer"], MATRIX_VIEWPORT_COL_BUFFER)
