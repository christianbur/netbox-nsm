"""Tests for TypeConfig YAML export."""

import yaml
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from dcim.models import Device, Interface, Rack, Region, Site
from ipam.models import IPAddress, Prefix, VLAN, VRF
from virtualization.models import VirtualMachine

from netbox_nsm.type_metadata.config import (
    NsmTypeConfig,
    config_dict_from_metadata_block,
    metadata_block_for_cot_slug,
)
from netbox_nsm.type_metadata.specs import REQUIRED_COT_SLUGS, TYPECONFIG_LIST_EXCLUDED_SLUGS
from netbox_nsm.type_metadata.export import (
    apply_schema_bundle_metadata,
    build_all_type_configs_preview_rows,
    build_type_config_export_data,
    build_type_config_preview_rows,
    content_type_export_ref,
    cot_slug_for_content_type,
    export_all_type_configs_yaml,
    export_type_config_yaml,
    format_all_type_configs_comment_yaml,
    format_type_config_comment_yaml,
    format_type_config_comment_yaml_for_metadata_block,
    format_type_config_comment_yaml_for_config,
)
from netbox_nsm.tests.rulebook_permission_helpers import grant_nsm_config_perms
from netbox_nsm.type_metadata.views import TypeMetadataListEntry
from utilities.testing import TestCase


def _parse_export_sections(yaml_text: str) -> list[dict]:
    """Parse multi-section export YAML into one dict per Object Config."""
    from netbox_nsm.type_metadata.config import (
        _load_yaml_document,
        normalize_nsm_config_list,
    )

    sections: list[dict] = []
    for block in yaml_text.strip().split("\n\n"):
        data = _load_yaml_document(block)
        sections.append(normalize_nsm_config_list(data["nsm_config"]))
    return sections


class TypeConfigExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)
        cls.type_config = NsmTypeConfig(
            slug="nsm_zone",
            content_type_id=cls.prefix_ct.pk,
            name="Test Zones",
            sort_order=10,
            display_template="{{ name }}",
        )

    def test_content_type_export_ref_uses_app_label_model(self):
        self.assertEqual(content_type_export_ref(self.prefix_ct), "ipam.prefix")

    @patch("netbox_nsm.type_metadata.export.cot_slug_for_content_type")
    def test_content_type_export_ref_prefers_slug(self, mock_slug):
        mock_slug.return_value = "nsm_zone"
        self.assertEqual(content_type_export_ref(self.prefix_ct), "nsm_zone")

    def test_build_export_data_contains_settings_only(self):
        data = build_type_config_export_data(self.type_config)
        self.assertEqual(
            data,
            {
                "sort_order": 10,
                "display_template": "{{ name }}",
            },
        )

    def test_export_yaml_format(self):
        yaml_text = export_type_config_yaml(self.type_config)
        self.assertIn("nsm_config:\n", yaml_text)
        self.assertIn("sort_order: 10\n", yaml_text)
        self.assertIn("display_template:", yaml_text)
        self.assertIn("{{ name }}", yaml_text)
        self.assertNotIn("# Test Zones", yaml_text)
        self.assertNotIn("name: Test Zones", yaml_text)
        self.assertNotIn("slug:", yaml_text)
        self.assertNotIn("content_type:", yaml_text)
        self.assertIn("rule_view:", yaml_text)

    def test_preview_rows_include_core_fields(self):
        rows = build_type_config_preview_rows(self.type_config)
        labels = [row["label"] for row in rows]
        self.assertIn("Name", labels)
        self.assertIn("Sort order", labels)
        self.assertIn("Display Template", labels)

    def test_cot_slug_for_non_custom_objects_content_type(self):
        self.assertIsNone(cot_slug_for_content_type(self.prefix_ct))

    @patch("netbox_custom_objects.models.CustomObjectType.objects.filter")
    def test_cot_slug_for_custom_objects_model(self, mock_filter):
        ct = ContentType(app_label="netbox_custom_objects", model="table42model")
        mock_filter.return_value.only.return_value.first.return_value = type(
            "COT", (), {"slug": "nsm_zone"}
        )()
        self.assertEqual(cot_slug_for_content_type(ct), "nsm_zone")
        mock_filter.assert_called_once_with(pk=42)


class TypeConfigAllExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)
        cls.configs: list[NsmTypeConfig] = []
        for slug in REQUIRED_COT_SLUGS:
            if slug in TYPECONFIG_LIST_EXCLUDED_SLUGS:
                continue
            block = metadata_block_for_cot_slug(slug)
            if not block:
                continue
            cfg_dict = config_dict_from_metadata_block(block)
            cls.configs.append(
                NsmTypeConfig(
                    slug=slug,
                    content_type_id=cls.prefix_ct.pk,
                    name=slug,
                    sort_order=cfg_dict["sort_order"],
                    display_template=cfg_dict["display_template"],
                )
            )
        cls.configs.sort(key=lambda cfg: (cfg.sort_order, cfg.name))

    def _patch_configs(self):
        return patch(
            "netbox_nsm.type_metadata.export._resolved_ui_configs",
            return_value=self.configs,
        )

    def test_export_all_yaml_has_ten_configs(self):
        with self._patch_configs():
            sections = _parse_export_sections(export_all_type_configs_yaml())
        self.assertEqual(len(sections), 10)

    def test_export_all_yaml_sorted_by_sort_order(self):
        with self._patch_configs():
            sections = _parse_export_sections(export_all_type_configs_yaml())
        sort_orders = [row["sort_order"] for row in sections]
        self.assertEqual(sort_orders, sorted(sort_orders))
        self.assertEqual(sections[0]["sort_order"], 10)
        self.assertEqual(sections[-1]["sort_order"], 40)

    def test_export_all_yaml_includes_all_ui_types_except_object_link(self):
        with self._patch_configs():
            sections = _parse_export_sections(export_all_type_configs_yaml())
        slugs = {cfg.slug for cfg in self.configs}
        self.assertNotIn("nsm_object_link", slugs)
        self.assertEqual(len(sections), 10)

    def test_preview_rows_match_export_count(self):
        with self._patch_configs():
            rows = build_all_type_configs_preview_rows()
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0]["slug"], "nsm_zone")
        self.assertEqual(rows[0]["sort_order"], 10)

    def test_export_all_yaml_contains_rule_view_settings(self):
        with self._patch_configs():
            sections = _parse_export_sections(export_all_type_configs_yaml())
        for entry in sections:
            self.assertIn("sort_order", entry)
            self.assertIn("display_template", entry)

    def test_list_view_excludes_export_panel(self):
        grant_nsm_config_perms(self, view=True)
        entries = [
            TypeMetadataListEntry(config=cfg, has_stored_metadata=True)
            for cfg in self.configs
        ]
        with patch(
            "netbox_nsm.type_metadata.views._resolved_configs",
            return_value=entries,
        ):
            response = self.client.get(reverse("plugins:netbox_nsm:typemetadata_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Settings export")


class TypeConfigCommentYamlTests(TestCase):
    def test_format_type_config_comment_yaml(self):
        yaml_text = format_type_config_comment_yaml(10, "{{ name }}")
        self.assertIn("nsm_config:", yaml_text)
        self.assertIn("rule_view:", yaml_text)
        self.assertIn("sort_order: 10", yaml_text)
        self.assertIn("display_template:", yaml_text)
        self.assertIn("{{ name }}", yaml_text)

    def test_format_type_config_comment_yaml_for_metadata_block(self):
        block = metadata_block_for_cot_slug("nsm_zone")
        self.assertIsNotNone(block)
        yaml_text = format_type_config_comment_yaml_for_metadata_block(block)
        self.assertNotIn("# ", yaml_text)
        self.assertIn("sort_order: 10\n", yaml_text)
        self.assertIn("display_template:", yaml_text)

    def test_format_all_type_configs_comment_yaml_has_ten_sections(self):
        sections = _parse_export_sections(format_all_type_configs_comment_yaml())
        self.assertEqual(len(sections), 10)
        self.assertEqual(sections[0]["sort_order"], 10)
        self.assertEqual(sections[-1]["sort_order"], 40)

    def test_comment_yaml_matches_export_format(self):
        type_config = NsmTypeConfig(
            slug="nsm_zone",
            content_type_id=ContentType.objects.get_for_model(Prefix).pk,
            name="Test Zones",
            sort_order=10,
            display_template="{{ name }}",
        )
        comment_yaml = format_type_config_comment_yaml_for_config(type_config)
        export_yaml = export_type_config_yaml(type_config)
        self.assertEqual(comment_yaml.rstrip(), export_yaml.rstrip())

    def test_apply_schema_bundle_metadata_writes_comments(self):
        try:
            from netbox_custom_objects.models import CustomObjectType
        except ImportError:
            self.skipTest("netbox_custom_objects not installed")

        cot = CustomObjectType.objects.create(
            name="nsm_zone",
            slug="nsm_zone",
            verbose_name="Zones",
        )
        counts = apply_schema_bundle_metadata()
        self.assertGreaterEqual(counts.get("types", 0), 1)
        cot.refresh_from_db()
        self.assertIn("nsm_config:", cot.comments)

    def test_object_link_metadata_has_no_rule_view(self):
        block = metadata_block_for_cot_slug("nsm_object_link")
        self.assertIsNotNone(block)
        self.assertTrue(block.get("link_table"))
        self.assertNotIn("rule_view", block)
