"""Matrix cell links → Rules tab nsm_q + AG Grid filters."""

from types import SimpleNamespace
from urllib.parse import parse_qs, unquote, urlparse

from django.test import SimpleTestCase

from netbox_nsm.views.rulebook import _matrix_policy_href


class MatrixPolicyHrefTests(SimpleTestCase):
    def test_href_uses_display_template_and_type_segment(self):
        zone_a = SimpleNamespace(name="dmz", label_type="prod")
        zone_b = SimpleNamespace(name="app", label_type="lan")
        tmpl = {99: "{label_type!u}:{name}"}
        href = _matrix_policy_href(
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
        self.assertIn("Source.Zones.name", nsm_q)
        self.assertIn("Destination.Zones.name", nsm_q)
