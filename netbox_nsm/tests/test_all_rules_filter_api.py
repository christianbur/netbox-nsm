"""All-rules filter API: separated rulebook scope + deprecated colon scope."""

import json
from urllib.parse import quote

from django.test import RequestFactory
from django.urls import reverse

from netbox_nsm.models import Rule, Rulebook
from netbox_nsm.policy_grid_payload import SCOPED_FILTER_FORMAT_ERROR
from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields
from utilities.testing import TestCase
from netbox_nsm.views.all_rules_grid_api import AllRulesGridApiView
from netbox_nsm.views.all_rules_query_validate_api import AllRulesQueryValidateApiView


class AllRulesFilterApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="Prod FW",
            rulebook_type="policy",
        )
        cls.other_rulebook = Rulebook.objects.create(
            name="Staging FW",
            rulebook_type="policy",
        )
        ensure_system_rulebook_fields(cls.rulebook)
        ensure_system_rulebook_fields(cls.other_rulebook)
        Rule.objects.create(rulebook=cls.rulebook, name="test-rule", index=10)
        Rule.objects.create(rulebook=cls.other_rulebook, name="other-rule", index=20)

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.add_permissions("netbox_nsm.view_rule")
        self.grid_url = reverse("plugins:netbox_nsm:all_rules_grid_api")
        self.validate_url = reverse("plugins:netbox_nsm:all_rules_query_validate_api")

    def _get_json(self, view_cls, url):
        request = self.factory.get(url)
        request.user = self.user
        response = view_cls.as_view()(request)
        return response.status_code, json.loads(response.content)

    def test_validate_rejects_bracket_scope(self):
        q = quote('["Prod FW", Name(kkk OR mm)]', safe="")
        status, data = self._get_json(
            AllRulesQueryValidateApiView,
            f"{self.validate_url}?q={q}",
        )
        self.assertEqual(status, 400)
        self.assertFalse(data["valid"])
        self.assertEqual(data["error"], SCOPED_FILTER_FORMAT_ERROR)

    def test_validate_accepts_colon_scope_deprecated(self):
        q = quote('"Prod FW": Name(test)', safe="")
        status, data = self._get_json(
            AllRulesQueryValidateApiView,
            f"{self.validate_url}?q={q}",
        )
        self.assertEqual(status, 200)
        self.assertTrue(data["valid"])
        self.assertEqual(data["rulebook"], "Prod FW")
        self.assertEqual(data["rulebookId"], self.rulebook.pk)
        self.assertEqual(data["filterQ"], "Name(test)")
        self.assertEqual(data["normalized"], "Name(test)")

    def test_validate_rulebook_id_and_filter_q(self):
        status, data = self._get_json(
            AllRulesQueryValidateApiView,
            f"{self.validate_url}?rulebook_id={self.rulebook.pk}&filter_q=Name(test)",
        )
        self.assertEqual(status, 200)
        self.assertTrue(data["valid"])
        self.assertEqual(data["rulebook"], "Prod FW")
        self.assertEqual(data["rulebookId"], self.rulebook.pk)
        self.assertEqual(data["filterQ"], "Name(test)")

    def test_validate_rulebook_name_and_filter_q(self):
        rb = quote("Prod FW", safe="")
        fq = quote("Name(test)", safe="")
        status, data = self._get_json(
            AllRulesQueryValidateApiView,
            f"{self.validate_url}?rulebook={rb}&filter_q={fq}",
        )
        self.assertEqual(status, 200)
        self.assertTrue(data["valid"])
        self.assertEqual(data["rulebook"], "Prod FW")
        self.assertEqual(data["filterQ"], "Name(test)")

    def test_rulebook_id_beats_rulebook_name(self):
        status, data = self._get_json(
            AllRulesQueryValidateApiView,
            f"{self.validate_url}?rulebook_id={self.rulebook.pk}"
            f"&rulebook={quote('Staging FW', safe='')}&filter_q=Name(test)",
        )
        self.assertEqual(status, 200)
        self.assertTrue(data["valid"])
        self.assertEqual(data["rulebookId"], self.rulebook.pk)
        self.assertEqual(data["rulebook"], "Prod FW")

    def test_explicit_rulebook_ignores_scoped_prefix_in_filter_q(self):
        scoped = quote('"Staging FW": Name(ignored)', safe="")
        status, data = self._get_json(
            AllRulesQueryValidateApiView,
            f"{self.validate_url}?rulebook_id={self.rulebook.pk}&filter_q={scoped}",
        )
        self.assertEqual(status, 200)
        self.assertTrue(data["valid"])
        self.assertEqual(data["rulebookId"], self.rulebook.pk)
        self.assertEqual(data["filterQ"], "Name(ignored)")

    def test_validate_unknown_rulebook_name(self):
        status, data = self._get_json(
            AllRulesQueryValidateApiView,
            f"{self.validate_url}?rulebook=Missing&filter_q=Name(x)",
        )
        self.assertEqual(status, 400)
        self.assertFalse(data["valid"])
        self.assertIn("Unknown rulebook", data["error"])

    def test_grid_rejects_bracket_scope(self):
        q = quote('["Prod FW", Name(test)]', safe="")
        status, data = self._get_json(
            AllRulesGridApiView,
            f"{self.grid_url}?filter_q={q}",
        )
        self.assertEqual(status, 400)
        self.assertEqual(data["error"], SCOPED_FILTER_FORMAT_ERROR)

    def test_grid_accepts_colon_scope_deprecated(self):
        fq = quote('"Prod FW": (test-rule)', safe="")
        status, data = self._get_json(
            AllRulesGridApiView,
            f"{self.grid_url}?filter_q={fq}&startRow=0&endRow=50",
        )
        self.assertEqual(status, 200)
        self.assertIn("rowData", data)
        self.assertEqual(data["lastRow"], 1)

    def test_grid_rulebook_id_and_filter_q(self):
        status, data = self._get_json(
            AllRulesGridApiView,
            f"{self.grid_url}?rulebook_id={self.rulebook.pk}"
            f"&filter_q=(test-rule)&startRow=0&endRow=50",
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["lastRow"], 1)

    def test_grid_rulebook_name_and_filter_q(self):
        rb = quote("Prod FW", safe="")
        status, data = self._get_json(
            AllRulesGridApiView,
            f"{self.grid_url}?rulebook={rb}&filter_q=(test-rule)&startRow=0&endRow=50",
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["lastRow"], 1)

    def test_validate_canonical_rulebook_and_bare_name(self):
        fq = quote('Rulebook("Prod FW") AND (test-rule)', safe="")
        status, data = self._get_json(
            AllRulesQueryValidateApiView,
            f"{self.validate_url}?filter_q={fq}",
        )
        self.assertEqual(status, 200)
        self.assertTrue(data["valid"])
        self.assertEqual(
            data["normalized"],
            'Rulebook("Prod FW") AND (test-rule)',
        )

    def test_validate_normalizes_name_shorthand_to_bare_parens(self):
        fq = quote("Name(test-rule)", safe="")
        status, data = self._get_json(
            AllRulesQueryValidateApiView,
            f"{self.validate_url}?filter_q={fq}",
        )
        self.assertEqual(status, 200)
        self.assertTrue(data["valid"])
        self.assertEqual(data["normalized"], "(test-rule)")

    def test_validate_policy_style_still_valid_when_scoped(self):
        status, data = self._get_json(
            AllRulesQueryValidateApiView,
            f"{self.validate_url}?rulebook_id={self.rulebook.pk}&filter_q=Name(test)",
        )
        self.assertEqual(status, 200)
        self.assertTrue(data["valid"])
        self.assertEqual(data["filterQ"], "Name(test)")

    def test_grid_canonical_filter_q(self):
        fq = quote('Rulebook("Prod FW") AND (test-rule)', safe="")
        status, data = self._get_json(
            AllRulesGridApiView,
            f"{self.grid_url}?filter_q={fq}&startRow=0&endRow=50",
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["lastRow"], 1)

    def test_grid_rulebook_scope_without_body(self):
        status, data = self._get_json(
            AllRulesGridApiView,
            f"{self.grid_url}?rulebook_id={self.rulebook.pk}&startRow=0&endRow=50",
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["lastRow"], 1)
