"""Stress test: bulk rule create, random edit, random delete."""

import random

from rest_framework import status

from netbox_nsm.models import Rule, Rulebook
from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields
from netbox_nsm.tests.custom import APITestCase
from netbox_nsm.tests.test_api_integration import (
    _API_CRUD_PERMS,
    _RulebookPluginAPITestMixin,
    _api,
)

RULE_COUNT = 100
RANDOM_SEED = 42
EDIT_COUNT = 35
DELETE_COUNT = 25


class RulesBulkRandomStressTest(_RulebookPluginAPITestMixin, APITestCase):
    """Create 100 rules, randomly edit/delete subsets, verify DB integrity."""

    def test_bulk_create_random_edit_delete(self):
        self._grant(*_API_CRUD_PERMS)
        rng = random.Random(RANDOM_SEED)

        rb_resp = self._post_json(
            _api("rulebook-list"),
            {"name": "bulk-random-rb", "rulebook_type": "security_rules"},
        )
        self.assertEqual(rb_resp.status_code, status.HTTP_201_CREATED, rb_resp.data)
        rb_id = rb_resp.data["id"]
        ensure_system_rulebook_fields(Rulebook.objects.get(pk=rb_id))

        expected_by_index: dict[int, dict] = {}
        for index in range(1, RULE_COUNT + 1):
            name = f"bulk-rule-{index:03d}"
            rule_index = index * 10
            resp = self._post_json(
                _api("rule-list"),
                {
                    "rulebook": rb_id,
                    "name": name,
                    "index": rule_index,
                    "enabled": True,
                },
            )
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
            expected_by_index[index] = {
                "pk": resp.data["id"],
                "name": name,
                "index": rule_index,
                "enabled": True,
            }

        self.assertEqual(Rule.objects.filter(rulebook_id=rb_id).count(), RULE_COUNT)

        edit_indices = set(rng.sample(list(expected_by_index.keys()), EDIT_COUNT))
        for index in sorted(edit_indices):
            state = expected_by_index[index]
            new_name = f"{state['name']}-edited"
            new_enabled = not state["enabled"]
            resp = self._patch_json(
                _api("rule-detail", pk=state["pk"]),
                {"name": new_name, "enabled": new_enabled},
            )
            self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
            state["name"] = new_name
            state["enabled"] = new_enabled

        delete_indices = set(rng.sample(list(expected_by_index.keys()), DELETE_COUNT))
        for index in sorted(delete_indices):
            pk = expected_by_index[index]["pk"]
            resp = self._delete(_api("rule-detail", pk=pk))
            self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
            del expected_by_index[index]

        remaining_count = RULE_COUNT - DELETE_COUNT
        self.assertEqual(len(expected_by_index), remaining_count)
        self.assertEqual(
            Rule.objects.filter(rulebook_id=rb_id).count(),
            remaining_count,
        )

        remaining_pks = {state["pk"] for state in expected_by_index.values()}
        self.assertEqual(
            set(Rule.objects.filter(rulebook_id=rb_id).values_list("pk", flat=True)),
            remaining_pks,
        )

        for expected in expected_by_index.values():
            rule = Rule.objects.get(pk=expected["pk"])
            self.assertEqual(rule.name, expected["name"])
            self.assertEqual(rule.index, expected["index"])
            self.assertEqual(rule.enabled, expected["enabled"])
            self.assertEqual(rule.rulebook_id, rb_id)

        list_resp = self.client.get(
            _api("rule-list") + f"?rulebook_id={rb_id}",
            **self.header,
        )
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(list_resp.data["count"], remaining_count)

        Rulebook.objects.filter(pk=rb_id).delete()
