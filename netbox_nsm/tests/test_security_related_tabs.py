"""Tests for Security tab related-tabs row resolution (PR #482 pattern)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.security.tab.cot_metadata import cot_link_table_flag
from netbox_nsm.security.tab.combined import (
    _JunctionField,
    _OutgoingFieldProxy,
    _outgoing_rows,
    _transform_junctions,
)


class CotLinkTableFlagTests(SimpleTestCase):
    def test_native_link_table_field(self):
        cot = SimpleNamespace(link_table=True, comments="", metadata="")
        self.assertTrue(cot_link_table_flag(cot))

    @patch(
        "netbox_nsm.objects.nsm_config.resolve_nsm_config_dict_for_cot",
        return_value={"links": {"link_table": True}},
    )
    def test_link_table_from_nsm_config_links_block(self, _mock_cfg):
        cot = SimpleNamespace(link_table=False, comments="nsm_config:", metadata="")
        self.assertTrue(cot_link_table_flag(cot))

    @patch(
        "netbox_nsm.security.tab.cot_metadata._link_table_from_nsm_config_comments",
        return_value=False,
    )
    def test_link_table_from_metadata_yaml(self, _mock_comments):
        cot = SimpleNamespace(link_table=False, comments="", metadata="link_table: true\n")
        self.assertTrue(cot_link_table_flag(cot))


class OutgoingRowsTests(SimpleTestCase):
    @patch("netbox_nsm.security.tab.combined._object_fields_for_cot")
    @patch("netbox_nsm.security.tab.combined._field_has_value", return_value=True)
    @patch("netbox_nsm.security.tab.combined.cot_link_table_flag", return_value=False)
    def test_outgoing_proxy_label(self, _mock_junction, _mock_has, mock_fields):
        field = SimpleNamespace(name="target", __str__=lambda self: "Target")
        mock_fields.return_value = [field]
        host = SimpleNamespace(custom_object_type=SimpleNamespace(slug="addr"))
        rows = _outgoing_rows(host)
        self.assertEqual(len(rows), 1)
        row_obj, proxy = rows[0]
        self.assertIs(row_obj, host)
        self.assertIsInstance(proxy, _OutgoingFieldProxy)
        self.assertIn("\u2192", str(proxy))


class TransformJunctionsTests(SimpleTestCase):
    @patch("netbox_nsm.security.tab.combined.cot_link_table_flag", return_value=True)
    @patch("netbox_nsm.security.tab.combined._far_field")
    def test_rewrites_junction_to_far_endpoint(self, mock_far, _mock_flag):
        endpoint = SimpleNamespace(
            pk=99,
            get_absolute_url=lambda: "/devices/1/",
            custom_object_type=None,
            _meta=SimpleNamespace(verbose_name="device"),
        )
        junction = SimpleNamespace(pk=5)
        near_field = SimpleNamespace(name="host", custom_object_type=SimpleNamespace(slug="link"))
        far_field = SimpleNamespace(name="endpoint")
        mock_far.return_value = far_field
        junction.endpoint = endpoint

        rows = _transform_junctions([(junction, near_field)])
        self.assertEqual(len(rows), 1)
        obj, field = rows[0]
        self.assertIs(obj, endpoint)
        self.assertIsInstance(field, _JunctionField)
        self.assertIs(field.via_obj, junction)

    @patch("netbox_nsm.security.tab.combined.cot_link_table_flag", return_value=True)
    @patch("netbox_nsm.security.tab.combined._far_field", return_value=None)
    def test_unresolved_junction_left_untouched(self, _mock_far, _mock_flag):
        junction = SimpleNamespace(pk=5)
        near_field = SimpleNamespace(name="host", custom_object_type=SimpleNamespace())
        rows = _transform_junctions([(junction, near_field)])
        self.assertEqual(rows, [(junction, near_field)])

    @patch(
        "netbox_nsm.security.tab.combined.cot_link_table_flag",
        side_effect=RuntimeError("boom"),
    )
    def test_transform_is_defensive(self, _mock_flag):
        row = (SimpleNamespace(pk=1), SimpleNamespace(custom_object_type=SimpleNamespace()))
        self.assertEqual(_transform_junctions([row]), [row])
