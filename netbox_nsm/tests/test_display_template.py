"""Tests for Jinja2 display templates in NSM metadata."""

from types import SimpleNamespace

from django.core.exceptions import ValidationError

from netbox_nsm.core.display_template import (
    DEFAULT_DISPLAY_TEMPLATE,
    normalize_display_template,
    render_display_template,
    validate_display_template,
)
from netbox_nsm.core.display_utils import apply_display_template
from netbox_nsm.type_metadata.config import normalize_nsm_config_list
from utilities.testing import TestCase


class DisplayTemplateRenderTests(TestCase):
    def test_render_simple_name(self):
        obj = SimpleNamespace(name="web-01")
        self.assertEqual(
            render_display_template(obj, "{{ name }}"),
            "web-01",
        )

    def test_render_service_template(self):
        obj = SimpleNamespace(name="HTTPS", protocol="tcp", port=443)
        self.assertEqual(
            render_display_template(
                obj,
                "{{ name }} ({{ protocol }}/{{ port }})",
            ),
            "HTTPS (tcp/443)",
        )

    def test_render_upper_filter(self):
        obj = SimpleNamespace(name="permit")
        self.assertEqual(
            render_display_template(obj, "{{ name | upper }}"),
            "PERMIT",
        )

    def test_invalid_template_raises_on_validate(self):
        with self.assertRaises(ValidationError):
            validate_display_template("{% bad %}")

    def test_normalize_nsm_config_keeps_jinja2_template(self):
        config = normalize_nsm_config_list(
            [{"rule_view": {"display_template": "{{ name | upper }}", "sort_order": 1}}]
        )
        self.assertEqual(config["display_template"], "{{ name | upper }}")

    def test_default_template_constant(self):
        self.assertEqual(DEFAULT_DISPLAY_TEMPLATE, "{{ name }}")
        self.assertEqual(normalize_display_template(""), DEFAULT_DISPLAY_TEMPLATE)
        self.assertEqual(normalize_display_template("  {{ name }}  "), "{{ name }}")

    def test_apply_display_template_uses_jinja2(self):
        obj = SimpleNamespace(name="trust")
        self.assertEqual(
            apply_display_template(obj, "{{ name }}"),
            "trust",
        )
