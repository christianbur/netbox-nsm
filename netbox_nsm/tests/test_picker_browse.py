"""Tests for server-side rule picker browse."""

import re
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.objects.picker_browse import (
    _apply_name_filter_regex,
    _filter_queryset_by_query,
    _resolve_short_name,
    serialize_picker_object,
)
from django.db.models import Q
from ipam.models import Prefix
from utilities.testing import TestCase


class PickerBrowseHelperTests(SimpleTestCase):
    def test_resolve_short_name_prefers_name(self):
        obj = SimpleNamespace(name="zone-a", prefix="10.0.0.0/8")
        self.assertEqual(_resolve_short_name(obj), "zone-a")

    def test_resolve_short_name_falls_back_to_prefix(self):
        obj = SimpleNamespace(prefix="10.0.0.0/8")
        self.assertEqual(_resolve_short_name(obj), "10.0.0.0/8")

    def test_apply_name_filter_regex(self):
        items = [
            {"name": "dmz", "display": "DMZ"},
            {"name": "internal", "display": "Internal"},
        ]
        filtered = _apply_name_filter_regex(items, "^DMZ")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["name"], "dmz")

    def test_apply_name_filter_regex_invalid_pattern(self):
        items = [{"name": "a", "display": "A"}]
        self.assertEqual(_apply_name_filter_regex(items, "[invalid"), items)

    @patch("netbox_nsm.objects.picker_browse.render_object_display", return_value="Shown")
    @patch("netbox_nsm.objects.picker_browse._object_color", return_value="#abc")
    def test_serialize_picker_object(self, _color, _display):
        obj = SimpleNamespace(pk=7, name="svc-http")
        payload = serialize_picker_object(obj, 12, {})
        self.assertEqual(payload["id"], 7)
        self.assertEqual(payload["name"], "svc-http")
        self.assertEqual(payload["display"], "Shown")
        self.assertEqual(payload["color"], "#abc")

    def test_filter_queryset_by_query_uses_name(self):
        qs = MagicMock()
        model = MagicMock()
        field = MagicMock()

        def get_field(name):
            if name == "name":
                return field
            raise Exception("missing")

        model._meta.get_field.side_effect = get_field
        filtered = _filter_queryset_by_query(qs, model, "dmz")
        qs.filter.assert_called_once()
        call_arg = qs.filter.call_args[0][0]
        self.assertIsInstance(call_arg, Q)
        self.assertIs(filtered, qs.filter.return_value)

    def test_filter_queryset_by_query_no_fields(self):
        qs = MagicMock()
        model = MagicMock()
        model._meta.get_field.side_effect = Exception("missing")
        filtered = _filter_queryset_by_query(qs, model, "x")
        self.assertIs(filtered, qs.none.return_value)

    def test_name_filter_regex_compiles_like_js(self):
        pattern = "^prod"
        rx = re.compile(pattern)
        self.assertTrue(rx.search("prod-web"))
        self.assertFalse(rx.search("dev-web"))


class PickerBrowseQueryTests(TestCase):
    def test_filter_queryset_by_query_prefix_single_char(self):
        prefix = Prefix.objects.create(prefix="10.60.0.0/24", status="active")
        filtered = _filter_queryset_by_query(Prefix.objects.all(), Prefix, "1")
        self.assertIn(prefix, filtered)
