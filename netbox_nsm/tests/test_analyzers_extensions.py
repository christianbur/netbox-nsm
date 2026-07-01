"""Phase E: label analyzer skeleton + custom object-report check hook."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from netbox_nsm.analyzers.ip_analyzer.capability import IP_ANALYZER_KEY, ip_analyzer_spec
from netbox_nsm.analyzers.label import build_label_analysis, label_analyzer_spec
from netbox_nsm.analyzers.object_report.check_registry import (
    ObjectReportContext,
    clear_object_report_checks,
    register_object_report_check,
    run_extra_object_report_checks,
)
from netbox_nsm.analyzers.object_report.object_report import (
    prepare_object_report_check_rows,
)
from netbox_nsm.analyzers.registry import ANALYZER_BY_KEY


class IpAnalyzerRegistryTests(SimpleTestCase):
    def test_ip_analyzer_spec_registered(self):
        spec = ip_analyzer_spec()
        self.assertIsNotNone(spec)
        self.assertEqual(spec.key, IP_ANALYZER_KEY)
        self.assertEqual(spec.capability, "analyzer.ip_analyzer")
        self.assertEqual(spec.url_name, "ip_analyzer_api")
        self.assertIn(IP_ANALYZER_KEY, ANALYZER_BY_KEY)


class LabelAnalyzerSkeletonTests(SimpleTestCase):
    def test_label_spec_registered(self):
        spec = label_analyzer_spec()
        self.assertIsNotNone(spec)
        self.assertEqual(spec.capability, "analyzer.label")
        self.assertIn("label", ANALYZER_BY_KEY)

    def test_build_label_analysis_lists_label_cots(self):
        cots = [SimpleNamespace(slug="corp_label"), SimpleNamespace(slug="nsm_label")]
        with patch(
            "netbox_nsm.objects.cot_roles.iter_cots_by_role",
            return_value=iter(cots),
        ):
            result = build_label_analysis()
        self.assertTrue(result["available"])
        self.assertEqual(result["capability"], "analyzer.label")
        self.assertEqual(result["label_cots"], ["corp_label", "nsm_label"])


class ObjectReportCheckHookTests(SimpleTestCase):
    def tearDown(self):
        clear_object_report_checks()

    def _context(self):
        return ObjectReportContext(
            addr_cot=None,
            addr_model=None,
            group_cot=None,
            sample_limit=10,
            chunk_size=100,
        )

    def test_registered_check_runs(self):
        def my_check(context):
            return {"enabled": True, "count": 2, "groups": [], "samples": [], "title": "Custom"}

        register_object_report_check("my_custom", my_check)
        results = run_extra_object_report_checks(self._context())
        self.assertIn("my_custom", results)
        self.assertEqual(results["my_custom"]["count"], 2)

    def test_failing_check_is_isolated(self):
        def boom(context):
            raise RuntimeError("nope")

        register_object_report_check("boom", boom)
        results = run_extra_object_report_checks(self._context())
        self.assertFalse(results["boom"]["enabled"])
        self.assertIn("Custom check failed", results["boom"]["note"])

    def test_prepare_rows_includes_extra_checks(self):
        checks = {
            "my_custom": {
                "enabled": True,
                "count": 1,
                "groups": [],
                "samples": [],
                "title": "Custom",
            }
        }
        rows = prepare_object_report_check_rows(checks)
        keys = [row["key"] for row in rows]
        self.assertIn("my_custom", keys)
