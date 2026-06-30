"""Tests for IPA YAML export serialization."""

import yaml
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.analyzers.ip_analyzer.ipa_yaml_export import (
    build_ipa_export_child_objects,
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

        self.assertEqual(document["ipa_export_version"], "2")
        self.assertEqual(document["mode"], "merge")

        displayed = document["displayed"]
        self.assertEqual(displayed["counts"]["leaf_count"], 2)
        self.assertEqual(displayed["objects"][0]["name"], "demo-addr")
        self.assertIn("all,demo-addr,10.0.0.1", displayed["copy_lines"])
        self.assertIn("demo-addr,10.0.0.1", displayed["copy_lines"])

        addr_node = displayed["addr_analysis"][0]["types"][0]["nodes"][0]
        self.assertEqual(addr_node["name"], "demo-addr")
        self.assertEqual(addr_node["ip"], "10.0.0.1")
        self.assertNotIn("url", addr_node)

        tree_node = displayed["object_tree"][0]
        self.assertEqual(tree_node["ip"], "10.0.0.1")
        self.assertNotIn("url", tree_node)

        # No child expansion provided -> additional section absent.
        self.assertNotIn("ipam_children", document)

    def test_build_ipa_export_document_includes_ipam_children_section(self):
        child_objects = [
            {
                "content_type": 10,
                "id": 42,
                "name": "demo-addr",
                "copy_lines": ["demo-addr,10.0.0.0/24"],
                "children": [
                    {
                        "name": "10.0.0.0/24",
                        "kind": "group",
                        "prefix_display_cidr": "10.0.0.0/24",
                        "ip_ref": {"str": "10.0.0.0/24", "url": "#"},
                        "lazy_load": True,
                        "copy_lines": ["demo-addr,10.0.0.0/24"],
                        "children": [
                            {
                                "name": "10.0.0.1/32",
                                "kind": "leaf",
                                "ip_ref": {"str": "10.0.0.1/32", "url": "#"},
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ]
        document = build_ipa_export_document(
            self._sample_payload(), child_objects=child_objects
        )

        # Primary section is still present and separate.
        self.assertIn("displayed", document)
        self.assertIn("object_tree", document["displayed"])

        section = document["ipam_children"]
        self.assertIn("description", section)
        entry = section["objects"][0]
        self.assertEqual(entry["name"], "demo-addr")
        self.assertEqual(entry["content_type"], 10)

        parent = entry["children"][0]
        self.assertEqual(parent["prefix_display_cidr"], "10.0.0.0/24")
        self.assertEqual(parent["ip"], "10.0.0.0/24")
        self.assertNotIn("url", parent)
        # Lazy nodes are flagged truncated so consumers know more exists.
        self.assertTrue(parent["truncated"])
        self.assertEqual(parent["children"][0]["ip"], "10.0.0.1/32")

    def test_build_ipa_export_document_skips_empty_ipam_children(self):
        document = build_ipa_export_document(
            self._sample_payload(),
            child_objects=[{"content_type": 10, "id": 42, "children": []}],
        )
        self.assertNotIn("ipam_children", document)

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
        self.assertIn("copy_lines", parsed["displayed"])
        self.assertIn("addr_analysis", parsed["displayed"])

    def test_ipa_export_filename_slugifies_title(self):
        filename = ipa_export_filename(
            {"mode": "merge", "objects": []},
            export_context={"title": "Rule 2/3"},
        )
        self.assertTrue(filename.endswith("-merge.yaml"))
        self.assertIn("rule", filename)

    @patch(
        "netbox_nsm.analyzers.ip_analyzer.ipa_ipam_tree._build_ipa_object_drilldown_nodes"
    )
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_build_ipa_export_child_objects_resolves_visible_objects(
        self, content_type_cls, drilldown_fn
    ):
        obj = MagicMock()
        obj.name = "demo-addr"
        model_cls = MagicMock()
        model_cls.objects.filter.return_value.first.return_value = obj
        ct = MagicMock()
        ct.model_class.return_value = model_cls
        content_type_cls.objects.get.return_value = ct

        drilldown_fn.return_value = (
            [
                {
                    "name": "10.0.0.1/32",
                    "kind": "leaf",
                    "ip_ref": {"str": "10.0.0.1/32"},
                    "children": [],
                }
            ],
            ["demo-addr,10.0.0.1/32"],
        )

        payload = {
            "object_tree": [
                {"name": "demo-addr", "ct": "10", "pk": "42", "children": []}
            ]
        }
        entries = build_ipa_export_child_objects(payload)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["content_type"], 10)
        self.assertEqual(entries[0]["id"], 42)
        self.assertEqual(entries[0]["children"][0]["name"], "10.0.0.1/32")
        drilldown_fn.assert_called_once_with(obj)

    def test_build_ipa_export_child_objects_empty_without_tree(self):
        self.assertEqual(build_ipa_export_child_objects({}), [])
        self.assertEqual(
            build_ipa_export_child_objects({"object_tree": []}), []
        )

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
