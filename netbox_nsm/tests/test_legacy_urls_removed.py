"""Legacy plugin URLs were removed; old paths must 404."""

from django.urls import NoReverseMatch, reverse

from utilities.testing import TestCase


class LegacyUrlRemovedTests(TestCase):
    def test_removed_url_names_do_not_reverse(self):
        removed_names = (
            "setup",
            "setup_schema_detail",
            "setup_schema_preview",
            "setup_schema_apply",
            "objectconfig_list",
            "objectconfig_add",
            "objectconfig",
            "objectconfig_edit",
            "objectconfig_delete",
                        "objectconfig_list_legacy",
            "ip_analysis",
            "audit_report_legacy_redirect",
            "all_rules_legacy_overview_redirect",
            "global_rules_search",
        )
        for name in removed_names:
            with self.subTest(name=name):
                with self.assertRaises(NoReverseMatch):
                    reverse(f"plugins:netbox_nsm:{name}")

    def test_removed_paths_return_404(self):
        legacy_paths = (
            "/plugins/netbox-nsm/setup/",
            "/plugins/netbox-nsm/setup/schema/nsm_schema/",
            "/plugins/netbox-nsm/type-config/",
            "/plugins/netbox-nsm/object-builder/",
            "/plugins/netbox-nsm/ip-analysis/",
            "/plugins/netbox-nsm/audit-report/",
            "/plugins/netbox-nsm/rulebooks/all-rules/",
            "/plugins/netbox-nsm/rules/search/",
            "/plugins/netbox-nsm/rulebooks/0/matrix/",
        )
        for path in legacy_paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404, response.content)
