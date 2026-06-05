"""Tests for object detail → rulebook field filter URLs."""

from types import SimpleNamespace
from urllib.parse import parse_qs, unquote, urlparse

from django.test import SimpleTestCase

from netbox_nsm.object_rules_utils import build_object_field_rules_filter_url


class ObjectFieldRulesFilterUrlTests(SimpleTestCase):
    def test_builds_typed_field_query(self):
        rulebook = SimpleNamespace(pk=5)
        field = SimpleNamespace(
            pk=1,
            name="Destination",
            type_configs=SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(
                        type_config=SimpleNamespace(
                            name="Zones",
                            content_type_id=99,
                        )
                    )
                ]
            ),
        )
        obj = SimpleNamespace(name="trust")
        ct = SimpleNamespace(pk=99)

        url = build_object_field_rules_filter_url(
            rulebook,
            field,
            obj,
            ct,
            display_template_map={99: "{name}"},
        )
        nsm_q = unquote(parse_qs(urlparse(url).query)["nsm_q"][0])
        self.assertIn("/rulebooks/5/rules/", url)
        self.assertIn("Destination.Zones.name", nsm_q)
        self.assertIn("trust", nsm_q)

    def test_builds_untyped_field_query(self):
        rulebook = SimpleNamespace(pk=3)
        field = SimpleNamespace(
            pk=2,
            name="Service",
            type_configs=SimpleNamespace(all=lambda: []),
        )
        obj = SimpleNamespace(name="HTTPS")
        ct = SimpleNamespace(pk=42)

        url = build_object_field_rules_filter_url(
            rulebook,
            field,
            obj,
            ct,
            display_template_map={42: "{name}"},
        )
        nsm_q = unquote(parse_qs(urlparse(url).query)["nsm_q"][0])
        self.assertIn("Service.Name", nsm_q)
        self.assertIn("HTTPS", nsm_q)
