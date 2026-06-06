"""Matrix cell links → Rules tab nsm_q + AG Grid filters."""

from types import SimpleNamespace
from urllib.parse import parse_qs, unquote, urlparse

from django.test import SimpleTestCase

from netbox_nsm.views.rulebook import _matrix_rules_href


class MatrixRulesHrefTests(SimpleTestCase):
    def test_href_uses_display_template_and_type_segment(self):
        zone_a = SimpleNamespace(name="dmz", label_type="prod")
        zone_b = SimpleNamespace(name="app", label_type="lan")
        tmpl = {99: "{label_type!u}:{name}"}
        href = _matrix_rules_href(
            "/plugins/netbox-nsm/rulebooks/1/rules/",
            "Source",
            "Destination",
            zone_a,
            zone_b,
            zone_content_type_id=99,
            type_segment="Zones",
            display_template_map=tmpl,
        )
        qs = parse_qs(urlparse(href).query)
        nsm_q = unquote(qs["nsm_q"][0])
        self.assertIn("PROD:dmz", nsm_q)
        self.assertIn("LAN:app", nsm_q)
        self.assertIn("Source.Zones(PROD:dmz)", nsm_q)
        self.assertIn("Destination.Zones(LAN:app)", nsm_q)

    def test_href_appends_nsm_q_with_ampersand_when_base_has_query(self):
        zone_a = SimpleNamespace(name="dmz")
        zone_b = SimpleNamespace(name="app")
        base = "/plugins/netbox-nsm/rulebooks/1/rules/?_branch=abc12345"
        href = _matrix_rules_href(
            base,
            "Source",
            "Destination",
            zone_a,
            zone_b,
            display_template_map={},
        )
        self.assertNotIn("??", href)
        self.assertIn("?_branch=abc12345&nsm_q=", href)
        qs = parse_qs(urlparse(href).query)
        self.assertEqual(qs["_branch"], ["abc12345"])
        self.assertTrue(qs["nsm_q"])

    def test_href_appends_nsm_q_with_ampersand_when_base_has_branch(self):
        zone_a = SimpleNamespace(name="dev-1", label_type="prod")
        zone_b = SimpleNamespace(name="dev-2", label_type="lan")
        href = _matrix_rules_href(
            "/plugins/netbox-nsm/rulebooks/14/rules/?_branch=i2m2urgq",
            "Source",
            "Destination",
            zone_a,
            zone_b,
            type_segment="Addresses",
            display_template_map={},
        )
        self.assertEqual(href.count("?"), 1)
        self.assertIn("?_branch=i2m2urgq&nsm_q=", href)
        self.assertNotIn("?nsm_q=", href.replace("&nsm_q=", ""))
