"""Tests for IPA YAML export serialization."""

import yaml
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from netbox_nsm.analysis.ipa_yaml_export import (
    build_ipa_export_document,
    ipa_export_filename,
    parse_export_context_from_request,
    serialize_ipa_export_yaml,
)


class IpaYamlExportTests(SimpleTestCase):
    def _sample_payload(self):
        return {
            "mode": "merge",
            "leaf_count": 2,
            "count_subnets": 1,
            "count_ranges": 0,
            "count_ips": 1,
            "count_duplicates": 0,
            "count_group_duplicates": 0,
            "objects": [{"ct": "10", "pk": "42", "name": "demo-addr"}],
            "addr_analysis": [
                {
                    "field_name": "",
                    "types": [
                        {
                            "type_name": "",
                            "leaf_count": 2,
                            "all_copy_lines": ["all,demo-addr,10.0.0.1"],
                            "nodes": [
                                {
                                    "name": "demo-addr",
                                    "url": "/a/42/",
                                    "kind": "leaf",
                                    "ip_ref": {"str": "10.0.0.1", "url": "#"},
                                    "copy_lines": ["all,demo-addr,10.0.0.1"],
                                    "children": [],
                                }
                            ],
                        }
                    ],
                }
            ],
            "object_tree": [
                {
                    "name": "demo-addr",
                    "url": "/a/42/",
                    "ct": "10",
                    "pk": "42",
                    "kind": "leaf",
                    "ip_ref": {"str": "10.0.0.1", "url": "#"},
                    "copy_lines": ["demo-addr,10.0.0.1"],
                    "children": [],
                }
            ],
        }

    def test_build_ipa_export_document_includes_trees_and_copy_lines(self):
        document = build_ipa_export_document(self._sample_payload())

        self.assertEqual(document["ipa_export_version"], "1")
        self.assertEqual(document["mode"], "merge")
        self.assertEqual(document["counts"]["leaf_count"], 2)
        self.assertEqual(document["objects"][0]["name"], "demo-addr")
        self.assertIn("all,demo-addr,10.0.0.1", document["copy_lines"])
        self.assertIn("demo-addr,10.0.0.1", document["copy_lines"])

        addr_node = document["addr_analysis"][0]["types"][0]["nodes"][0]
        self.assertEqual(addr_node["name"], "demo-addr")
        self.assertEqual(addr_node["ip"], "10.0.0.1")
        self.assertNotIn("url", addr_node)

        tree_node = document["object_tree"][0]
        self.assertEqual(tree_node["ip"], "10.0.0.1")
        self.assertNotIn("url", tree_node)

    def test_build_ipa_export_document_includes_context_and_title(self):
        document = build_ipa_export_document(
            self._sample_payload(),
            export_context={
                "title": "Rule 2/3",
                "rule_index": "2",
                "rule_name": "Allow HTTP",
                "column_position": "3",
            },
        )

        self.assertEqual(document["title"], "Rule 2/3")
        self.assertEqual(document["context"]["rule_index"], "2")
        self.assertEqual(document["context"]["rule_name"], "Allow HTTP")

    def test_serialize_ipa_export_yaml_is_valid_yaml(self):
        document = build_ipa_export_document(self._sample_payload())
        yaml_text = serialize_ipa_export_yaml(document)

        parsed = yaml.safe_load(yaml_text)
        self.assertEqual(parsed["mode"], "merge")
        self.assertIn("copy_lines", parsed)
        self.assertIn("addr_analysis", parsed)

    def test_ipa_export_filename_slugifies_title(self):
        filename = ipa_export_filename(
            {"mode": "merge", "objects": []},
            export_context={"title": "Rule 2/3"},
        )
        self.assertTrue(filename.endswith("-merge.yaml"))
        self.assertIn("rule", filename)

    def test_parse_export_context_from_request(self):
        request = MagicMock()
        request.GET = {
            "export_title": "Merged (2 objects)",
            "ctx_rule_index": "4",
            "ctx_rule_name": "Deny SSH",
            "ctx_col_position": "src",
        }

        context = parse_export_context_from_request(request)

        self.assertEqual(context["title"], "Merged (2 objects)")
        self.assertEqual(context["rule_index"], "4")
        self.assertEqual(context["rule_name"], "Deny SSH")
        self.assertEqual(context["column_position"], "src")
