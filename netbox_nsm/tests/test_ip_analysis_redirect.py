"""Tests for the legacy IP Analysis page redirect."""

from unittest.mock import MagicMock

from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from netbox_nsm.views.ip_analysis import IpAnalysisLegacyRedirectView


class IpAnalysisLegacyRedirectTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = IpAnalysisLegacyRedirectView.as_view()

    def _auth_request(self, path):
        request = self.factory.get(path)
        request.user = MagicMock(is_authenticated=True)
        return request

    def test_ip_analysis_url_still_reverses(self):
        self.assertEqual(
            reverse("plugins:netbox_nsm:ip_analysis"),
            "/plugins/netbox-nsm/ip-analysis/",
        )

    def test_redirects_to_object_analyzer_without_params(self):
        response = self.view(self._auth_request("/plugins/netbox-nsm/ip-analysis/"))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response["Location"],
            reverse("plugins:netbox_nsm:object_analyzer"),
        )

    def test_redirects_with_legacy_column_a_params(self):
        response = self.view(
            self._auth_request(
                "/plugins/netbox-nsm/ip-analysis/"
                "?ip_ct=10&ip_pk=42&ip_name=branch-a"
            )
        )
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response["Location"],
            reverse("plugins:netbox_nsm:object_analyzer")
            + "?ct=10&pk=42&name=branch-a",
        )

    def test_prefers_column_a_over_column_b(self):
        response = self.view(
            self._auth_request(
                "/plugins/netbox-nsm/ip-analysis/"
                "?ip_ct=10&ip_pk=1&ip2_ct=11&ip2_pk=2"
            )
        )
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].endswith("?ct=10&pk=1"))

    def test_falls_back_to_column_b_params(self):
        response = self.view(
            self._auth_request(
                "/plugins/netbox-nsm/ip-analysis/?ip2_ct=11&ip2_pk=7&ip2_name=dst"
            )
        )
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response["Location"],
            reverse("plugins:netbox_nsm:object_analyzer")
            + "?ct=11&pk=7&name=dst",
        )
