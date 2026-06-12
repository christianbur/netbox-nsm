"""Tests for Object Sync column quick-search filters."""

from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.objects.address_object_builder import SyncIssue
from netbox_nsm.views.object_sync_filters import (
    SYNC_FILTER_PREFIX,
    apply_sync_issue_filters,
    filter_model_from_request,
    sync_issue_filter_record,
)


class ObjectSyncFilterTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_filter_model_from_request_parses_sync_params(self):
        request = self.factory.get(
            "/plugins/netbox-nsm/object-sync/"
            f"?{SYNC_FILTER_PREFIX}category=missing"
        )
        model = filter_model_from_request(
            request,
            (
                {"field": "category", "param": f"{SYNC_FILTER_PREFIX}category"},
                {"field": "source", "param": f"{SYNC_FILTER_PREFIX}source"},
            ),
        )
        self.assertIn("category", model)
        self.assertNotIn("source", model)

    def test_apply_sync_issue_filters_supports_or_expression(self):
        issues = [
            SyncIssue(category="missing", source_key="ipam.ipaddress"),
            SyncIssue(category="orphan_nsm", source_key=None),
        ]
        filtered = apply_sync_issue_filters(
            issues,
            {
                "category": {
                    "filterType": "text",
                    "operator": "OR",
                    "conditions": [
                        {"filterType": "text", "type": "contains", "filter": "missing"},
                        {"filterType": "text", "type": "contains", "filter": "orphan"},
                    ],
                }
            },
        )
        self.assertEqual(len(filtered), 2)

    def test_sync_issue_filter_record_splits_expected_fields(self):
        issue = SyncIssue(
            category="missing",
            expected_name="N-10.0.0.0-24",
            expected_status="active",
        )
        record = sync_issue_filter_record(issue)
        self.assertEqual(record["expected_name"], "N-10.0.0.0-24")
        self.assertEqual(record["expected_status"], "active")
