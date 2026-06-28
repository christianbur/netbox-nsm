"""Tests for COT Security Panel rule reference scanning."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from django.test import SimpleTestCase

from netbox_nsm.security.references.cot_rule_references import (
    _field_allows_content_type,
    _panel_rulebook,
    _scan_field_instances,
    build_cot_security_rulebook_groups,
)
from netbox_nsm.security.object_rules import (
    build_cot_rule_name_column_filter_url,
    build_cot_rules_column_filter_url,
)


class CotSecurityPanelUrlTests(SimpleTestCase):
    def test_cot_name_filter_url(self):
        url = build_cot_rule_name_column_filter_url("nsm_rb_demo", "allow-web")
        self.assertIn("/rulebooks/cot/nsm_rb_demo/rules/", url)
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query["f_name"][0], "allow-web")

    def test_cot_column_filter_url(self):
        url = build_cot_rules_column_filter_url(
            "nsm_rb_demo",
            "source_zones::ct_12",
            "trust",
        )
        query = parse_qs(urlparse(url).query)
        self.assertIn("f_source_zones__ct_12", query)


class CotSecurityPanelGroupTests(SimpleTestCase):
    @patch("netbox_nsm.security.references.cot_rule_references._field_allows_content_type", return_value=True)
    @patch("netbox_nsm.security.references.cot_rule_references._count_field_references", return_value=1)
    @patch("netbox_nsm.security.references.cot_rule_references._iter_matching_security_fields")
    @patch("netbox_nsm.security.references.cot_rule_references._panel_field")
    @patch("netbox_nsm.security.references.cot_rule_references._panel_rulebook")
    def test_build_groups_without_rule_links(
        self,
        mock_panel_rulebook,
        mock_panel_field,
        mock_iter_fields,
        mock_count,
        _mock_allows,
    ):
        cot = MagicMock()
        cot.pk = 7
        cot.get_model.return_value = MagicMock()
        cot_field = MagicMock(pk=4, name="source_zones", weight=20)
        mock_iter_fields.return_value = [(cot, cot_field)]

        rulebook = SimpleNamespace(
            pk=7,
            slug="nsm_rb_demo",
            name="Demo Rulebook",
            get_rules_tab_url=lambda: "/rulebooks/cot/nsm_rb_demo/rules/",
        )
        field = SimpleNamespace(pk=4, name="Zones (Source)", slug="source_zones")
        mock_panel_rulebook.return_value = rulebook
        mock_panel_field.return_value = field

        data = build_cot_security_rulebook_groups(
            SimpleNamespace(pk=1),
            42,
            panel_url=lambda url: url,
        )

        self.assertEqual(data["unique_rules_total"], 1)
        self.assertEqual(len(data["rulebook_groups"]), 1)
        group = data["rulebook_groups"][0]
        self.assertEqual(group["rulebook"].name, "Demo Rulebook")
        field_group = group["field_groups"][0]
        self.assertEqual(field_group["field"].name, "Zones (Source)")
        self.assertEqual(field_group["rule_count"], 1)
        self.assertNotIn("rules", field_group)
        self.assertIn("nsm_rb_demo", group["rules_tab_url"])
        mock_count.assert_called_once()

    @patch("netbox_nsm.security.references.cot_rule_references._scan_field_instances")
    @patch("netbox_nsm.security.references.cot_rule_references._instances_for_field")
    @patch("netbox_nsm.security.references.cot_rule_references._count_field_references", return_value=2)
    @patch("netbox_nsm.security.references.cot_rule_references._iter_matching_security_fields")
    @patch("netbox_nsm.security.references.cot_rule_references._panel_field")
    @patch("netbox_nsm.security.references.cot_rule_references._panel_rulebook")
    def test_initial_render_skips_full_rule_scan(
        self,
        mock_panel_rulebook,
        mock_panel_field,
        mock_iter_fields,
        mock_count,
        mock_instances,
        mock_scan,
    ):
        cot = MagicMock()
        cot.pk = 7
        cot.get_model.return_value = MagicMock()
        cot_field = MagicMock(pk=4, name="addresses", weight=10)
        mock_iter_fields.return_value = [(cot, cot_field)]
        mock_panel_rulebook.return_value = SimpleNamespace(
            pk=7,
            slug="nsm_rb_bench",
            name="Bench",
            get_rules_tab_url=lambda: "/rules/",
        )
        mock_panel_field.return_value = SimpleNamespace(
            pk=4, name="Addresses", slug="addresses"
        )

        build_cot_security_rulebook_groups(
            SimpleNamespace(pk=1),
            1739,
            panel_url=lambda url: url,
        )

        mock_count.assert_called_once()
        mock_instances.assert_not_called()
        mock_scan.assert_not_called()


class ScanFieldInstancesTests(SimpleTestCase):
    @patch(
        "netbox_nsm.security.references.cot_rule_references._instances_via_through_table",
        side_effect=RuntimeError("through unavailable"),
    )
    @patch("netbox_nsm.security.references.cot_rule_references.ContentType")
    def test_returns_queryset_not_list(self, mock_content_type, _mock_through):
        mock_content_type.objects.get_for_model.return_value = SimpleNamespace(pk=10)

        related_obj = SimpleNamespace(pk=42)
        related_mgr = MagicMock()
        related_mgr.all.return_value = [related_obj]

        instance = MagicMock()
        instance.pk = 99
        instance.zones = related_mgr

        cot_field = SimpleNamespace(name="zones")
        content_type = SimpleNamespace(pk=10)

        filtered_qs = MagicMock()
        filtered_qs.count.return_value = 1
        model = MagicMock()
        model.objects.all.return_value.order_by.return_value = [instance]
        model.objects.filter.return_value.order_by.return_value = filtered_qs

        result = _scan_field_instances(model, cot_field, content_type, 42)

        model.objects.filter.assert_called_once_with(pk__in=[99])
        self.assertEqual(result.count(), 1)

    @patch("netbox_nsm.security.references.cot_rule_references._through_table_source_ids")
    def test_prefers_through_table_lookup(self, mock_source_ids):
        source_ids = [99, 100]
        mock_source_ids.return_value = source_ids
        filtered_qs = MagicMock()
        model = MagicMock()
        model.objects.filter.return_value.order_by.return_value = filtered_qs

        cot_field = SimpleNamespace(
            name="addresses",
            is_polymorphic=True,
            through_model_name="FakeThrough",
        )
        content_type = SimpleNamespace(pk=10)

        result = _scan_field_instances(model, cot_field, content_type, 42)

        mock_source_ids.assert_called_once_with(cot_field, content_type, 42)
        model.objects.filter.assert_called_once_with(pk__in=source_ids)
        self.assertIs(result, filtered_qs)


class CotFieldAllowsContentTypeTests(SimpleTestCase):
    def test_non_polymorphic_matching_type(self):
        ct = SimpleNamespace(app_label="netbox_custom_objects", model="table5model")
        content_type = SimpleNamespace(
            pk=5, app_label="netbox_custom_objects", model="table5model"
        )
        field = SimpleNamespace(
            type="multiobject",
            is_polymorphic=False,
            related_object_type=ct,
            related_object_types=SimpleNamespace(all=lambda: []),
        )
        self.assertTrue(_field_allows_content_type(field, content_type))

    def test_polymorphic_non_matching_type(self):
        allowed = SimpleNamespace(
            app_label="netbox_custom_objects", model="table5model"
        )
        content_type = SimpleNamespace(
            pk=9, app_label="dcim", model="device"
        )
        field = SimpleNamespace(
            type="multiobject",
            is_polymorphic=True,
            related_object_type=None,
            related_object_types=SimpleNamespace(all=lambda: [allowed]),
        )
        self.assertFalse(_field_allows_content_type(field, content_type))
