"""Matrix tab bulk prefetch for large COT rulebooks."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.matrix.cot_matrix_tab_context import build_cot_matrix_tab_context


class CotMatrixTabPrefetchTests(SimpleTestCase):
    @patch("netbox_nsm.matrix.cot_matrix_tab_context.build_sparse_matrix_cells")
    @patch("netbox_nsm.matrix.cot_matrix_tab_context.serialize_matrix_zone_axis")
    @patch("netbox_nsm.matrix.cot_matrix_tab_context._action_legend")
    @patch("netbox_nsm.matrix.cot_matrix_tab_context.resolve_matrix_object_type_selection")
    @patch("netbox_nsm.matrix.cot_matrix_tab_context.dedupe_matrix_object_types")
    @patch("netbox_nsm.matrix.cot_matrix_tab_context._matrix_available_types")
    @patch("netbox_nsm.matrix.cot_matrix_tab_context.prefetch_cot_multiobject_fields")
    @patch("netbox_nsm.matrix.cot_matrix_tab_context.cot_rule_instances_queryset")
    @patch("netbox_nsm.matrix.cot_matrix_tab_context.cot_rulebook_matrix_enabled")
    def test_build_prefetches_zone_and_action_fields(
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
        mock_serialize_axis.return_value = []
        mock_sparse_cells.return_value = {}

        fields = MagicMock()
        fields.values_list.return_value = ["source_zones", "destination_zones"]
        cot = SimpleNamespace(slug="nsm_rb_zone_matrix", fields=fields)
        virtual_rb = SimpleNamespace(cot=cot, slug="nsm_rb_zone_matrix")
        request = RequestFactory().get("/matrix/")

        with (
            patch(
                "netbox_nsm.matrix.cot_matrix_tab_context.get_display_template_map",
                return_value={},
            ),
            patch(
                "netbox_nsm.matrix.cot_matrix_tab_context.reverse",
                return_value="/rules/",
            ),
            patch(
                "netbox_nsm.matrix.cot_matrix_tab_context.with_branch_query",
                side_effect=lambda url, _req: url,
            ),
            patch(
                "netbox_nsm.matrix.cot_matrix_tab_context.ContentType"
            ) as mock_ct,
        ):
            mock_ct.DoesNotExist = Exception
            mock_ct.objects.get.side_effect = lambda pk: SimpleNamespace(
                pk=pk,
                model_class=lambda: None,
            )
            build_cot_matrix_tab_context(request, virtual_rb)

        mock_prefetch.assert_called_once_with(
            [rule],
            virtual_rb,
            ["source_zones", "destination_zones", "actions"],
        )
