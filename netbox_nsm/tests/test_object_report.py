"""Tests for the NSM daily object report (logic, job, view)."""

from __future__ import annotations

import uuid
from unittest import mock

from django.urls import reverse
from django.utils import timezone

from core.choices import JobStatusChoices
from core.models import Job
from netbox.registry import registry
from utilities.testing import TestCase

from netbox_nsm.object_report import object_report
from netbox_nsm.object_report.jobs import (
    OBJECT_REPORT_JOB_NAME,
    ObjectReportJob,
    get_latest_object_report_job,
    get_pending_object_report_job,
)
from netbox_nsm.tests.rulebook_permission_helpers import grant_nsm_config_perms


def _all_checks_fixture():
    """Stored-report ``checks`` payload covering *every* OBJECT_REPORT_CHECK_KEYS.

    Each check carries findings, a grouped breakdown and a detail sample so the
    view renderer and TOML exporter exercise the full schema — including the
    newer ``ipam_orphans`` (with ``literal_skipped``), ``empty_groups`` and
    ``single_member_groups`` checks that earlier fixtures omitted.
    """
    return {
        "status_mismatch": {
            "enabled": True,
            "count": 2,
            "title": "all-status-mismatch",
            "explicit_config": True,
            "checked": 10,
            "ignored": 1,
            "orphans": 0,
            "groups": [{"label": "active → deprecated", "count": 2}],
            "samples": [
                {
                    "name": "addr-status",
                    "url": "",
                    "expected": "deprecated",
                    "actual": "active",
                    "ipam_type": "ipaddress",
                }
            ],
        },
        "ipam_duplicates": {
            "enabled": True,
            "count": 1,
            "excess_objects": 1,
            "title": "all-ipam-duplicates",
            "groups": [{"label": "ipaddress", "count": 1}],
            "samples": [
                {
                    "name": "10.0.0.1",
                    "url": "",
                    "ipam_type": "ipaddress",
                    "address_count": 2,
                }
            ],
        },
        "ipam_orphans": {
            "enabled": True,
            "count": 3,
            "literal_skipped": 5,
            "title": "all-ipam-orphans",
            "groups": [],
            "samples": [{"name": "orphan-addr", "url": "", "kind": "address"}],
        },
        "multi_group": {
            "enabled": True,
            "count": 1,
            "title": "all-multi-group",
            "groups": [{"label": "in 2 groups", "count": 1, "group_count": 2}],
            "samples": [{"name": "multi-addr", "url": "", "group_count": 2}],
        },
        "empty_groups": {
            "enabled": True,
            "count": 2,
            "title": "all-empty-groups",
            "groups": [],
            "samples": [{"name": "empty-grp", "url": "", "kind": "group"}],
        },
        "single_member_groups": {
            "enabled": True,
            "count": 1,
            "title": "all-single-member-groups",
            "groups": [],
            "samples": [{"name": "single-grp", "url": "", "kind": "group"}],
        },
        "similar_groups": {
            "enabled": True,
            "count": 1,
            "checked_groups": 4,
            "title": "all-similar-groups",
            "groups": [{"label": "≥ 90%", "count": 1}],
            "samples": [
                {
                    "name": "grp-a ↔ grp-b",
                    "group_a": "grp-a",
                    "group_b": "grp-b",
                    "group_a_url": "",
                    "group_b_url": "",
                    "overlap": 3,
                    "overlap_ratio": 1.0,
                    "overlap_pct": 100,
                    "score": 0.9,
                    "size_a": 3,
                    "size_b": 3,
                }
            ],
        },
        "deprecated": {
            "enabled": True,
            "count": 1,
            "address_count": 1,
            "group_count": 0,
            "title": "all-deprecated",
            "groups": [{"label": "Addresses", "count": 1}],
            "samples": [{"name": "dep-addr", "url": "", "kind": "address"}],
        },
    }


class ObjectReportLogicTests(TestCase):
    def test_report_unavailable_without_cot(self):
        # The test database has no nsm_address COT deployed.
        report = object_report.build_object_report()
        self.assertFalse(report["available"])
        self.assertIn("nsm_address", report["message"])
        self.assertIn("generated_at", report)
        self.assertIn("version", report)

    def test_sample_helper_shape(self):
        entry = object_report._sample("foo", pk=3, url="/x/", extra={"kind": "address"})
        self.assertEqual(entry["name"], "foo")
        self.assertEqual(entry["pk"], 3)
        self.assertEqual(entry["url"], "/x/")
        self.assertEqual(entry["kind"], "address")

    def test_check_keys_match_builder(self):
        self.assertEqual(
            set(object_report.OBJECT_REPORT_CHECK_KEYS),
            {
                "status_mismatch",
                "ipam_duplicates",
                "ipam_orphans",
                "multi_group",
                "empty_groups",
                "single_member_groups",
                "similar_groups",
                "deprecated",
            },
        )

    def test_groups_are_similar_rules(self):
        similar = object_report._groups_are_similar
        self.assertFalse(similar(2, 3, 2))
        self.assertFalse(similar(3, 4, 2))
        self.assertTrue(similar(3, 3, 3))
        self.assertTrue(similar(4, 4, 3))
        self.assertFalse(similar(4, 4, 2))
        self.assertTrue(similar(4, 8, 3))
        self.assertFalse(similar(5, 8, 3))
        self.assertTrue(similar(5, 8, 4))
        self.assertTrue(similar(8, 8, 6))

    def test_member_identity_key_prefers_ipam(self):
        key = object_report._member_identity_key(
            addr_pk=9,
            address_content_type_id=12,
            address_object_id=34,
        )
        self.assertEqual(key, ("ipam", 12, 34))
        self.assertEqual(object_report._member_identity_key(addr_pk=9), ("addr", 9))

    def test_similarity_score_and_buckets(self):
        self.assertEqual(object_report._similarity_score(4, 4, 3), 0.6)
        self.assertEqual(object_report._overlap_ratio(4, 8, 3), 0.75)
        self.assertEqual(object_report._score_bucket_label(0.95), "≥ 90%")
        self.assertEqual(object_report._score_bucket_label(0.8), "75–89%")
        self.assertEqual(object_report._score_bucket_label(0.6), "50–74%")

    def test_prepare_check_rows_status_and_details(self):
        checks = {
            "status_mismatch": {
                "enabled": True,
                "count": 0,
                "title": "Status",
                "groups": [],
                "samples": [],
                "explicit_config": False,
                "checked": 5,
                "ignored": 0,
                "orphans": 0,
            },
            "ipam_duplicates": {
                "enabled": True,
                "count": 2,
                "title": "Dupes",
                "excess_objects": 2,
                "groups": [{"label": "ipaddress", "count": 2}],
                "samples": [{"name": "x"}],
            },
            "multi_group": {
                "enabled": False,
                "count": 0,
                "title": "Multi",
                "note": "not available",
                "groups": [],
                "samples": [],
            },
            "similar_groups": {
                "enabled": True,
                "count": 0,
                "title": "Similar",
                "checked_groups": 12,
                "groups": [],
                "samples": [],
            },
            "deprecated": {
                "enabled": True,
                "count": 0,
                "title": "Dep",
                "groups": [],
                "samples": [],
            },
        }
        rows = object_report.prepare_object_report_check_rows(checks, sample_limit=50)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["status"], "ok")
        self.assertEqual(rows[1]["status"], "findings")
        self.assertTrue(rows[1]["has_samples"])
        self.assertEqual(rows[2]["status"], "disabled")
        self.assertEqual(rows[2]["details"], ["not available"])
        self.assertEqual(rows[3]["status"], "ok")

    def test_prepare_check_rows_sort_by_findings(self):
        checks = {
            "status_mismatch": {"enabled": True, "count": 1, "title": "a", "groups": [], "samples": []},
            "ipam_duplicates": {"enabled": True, "count": 5, "title": "b", "groups": [], "samples": []},
            "multi_group": {"enabled": True, "count": 0, "title": "c", "groups": [], "samples": []},
            "similar_groups": {"enabled": True, "count": 0, "title": "e", "groups": [], "samples": []},
            "deprecated": {"enabled": True, "count": 2, "title": "d", "groups": [], "samples": []},
        }
        rows = object_report.prepare_object_report_check_rows(checks)
        from netbox_nsm.object_report.tables import ObjectReportCheckTable

        table = ObjectReportCheckTable(rows)
        table.order_by = ("-findings",)
        sorted_rows = [row.record for row in table.rows]
        self.assertEqual([r["count"] for r in sorted_rows], [5, 2, 1, 0, 0])

    def test_check_similar_groups_disabled_without_through(self):
        result = object_report._check_similar_groups(None, None, sample_limit=10)
        self.assertFalse(result["enabled"])
        self.assertEqual(result["count"], 0)

    def test_check_similar_groups_finds_pair(self):
        class FakeThrough:
            objects = None

            @staticmethod
            def values_list(*_args, **_kwargs):
                return FakeThrough

            @staticmethod
            def iterator(*, chunk_size):
                return iter([(1, 10), (1, 11), (1, 12), (2, 10), (2, 11), (2, 12)])

        class FakeAddrQs:
            def filter(self, pk__in):
                return self

            def values(self, *args):
                return [
                    {"pk": 10, "address_content_type_id": 5, "address_object_id": 100},
                    {"pk": 11, "address_content_type_id": 5, "address_object_id": 101},
                    {"pk": 12, "address_content_type_id": 5, "address_object_id": 102},
                ]

        class FakeAddrModel:
            objects = FakeAddrQs()

        class FakeGroupQs:
            def __init__(self, rows):
                self._rows = rows

            def filter(self, pk__in):
                allowed = set(pk__in)
                return FakeGroupQs([r for r in self._rows if r["id"] in allowed])

            def values(self, *_args, **_kwargs):
                return self._rows

            def __iter__(self):
                for row in self._rows:
                    obj = mock.Mock()
                    obj.pk = row["id"]
                    obj.get_absolute_url.return_value = f"/g/{row['id']}/"
                    yield obj

        class FakeGroupModel:
            objects = FakeGroupQs(
                [{"id": 1, "name": "grp-a"}, {"id": 2, "name": "grp-b"}]
            )

        group_cot = mock.Mock()
        group_cot.get_model.return_value = FakeGroupModel

        with mock.patch.object(
            object_report,
            "_group_membership_through",
            return_value=(FakeThrough, "group_id", "member_id"),
        ):
            result = object_report._check_similar_groups(
                group_cot, FakeAddrModel, sample_limit=10
            )

        self.assertTrue(result["enabled"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["checked_groups"], 2)
        self.assertEqual(len(result["samples"]), 1)
        self.assertEqual(result["samples"][0]["group_a"], "grp-a")
        self.assertEqual(result["samples"][0]["overlap"], 3)

    def test_check_ipam_orphans_excludes_literals(self):
        class FakeAddrQs:
            def __init__(self, rows):
                self._rows = rows

            def filter(self, **_kwargs):
                return self

            def values(self, *_args):
                return self

            def order_by(self, *_args):
                return self

            def iterator(self, *, chunk_size):
                return iter(self._rows)

        class FakeAddrModel:
            objects = FakeAddrQs(
                [
                    {"id": 1, "name": "orphan-1", "comments": ""},
                    {
                        "id": 2,
                        "name": "literal-any",
                        "comments": "nsm_config:\n  - network: 0.0.0.0/0\n",
                    },
                    {"id": 3, "name": "orphan-2", "comments": None},
                ]
            )

        result = object_report._check_ipam_orphans(
            FakeAddrModel, sample_limit=10, chunk_size=100
        )
        self.assertTrue(result["enabled"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["literal_skipped"], 1)
        self.assertEqual(
            sorted(s["name"] for s in result["samples"]),
            ["orphan-1", "orphan-2"],
        )

    def test_check_empty_groups_disabled_without_through(self):
        result = object_report._check_empty_groups(None, sample_limit=10)
        self.assertFalse(result["enabled"])
        self.assertEqual(result["count"], 0)

    def test_check_empty_groups_finds_unpopulated(self):
        class FakeDistinct:
            def distinct(self):
                return [1]

        class FakeThrough:
            class objects:
                @staticmethod
                def values_list(_field, flat=False):
                    return FakeDistinct()

        class FakeValuesQs:
            def __init__(self, rows):
                self._rows = rows

            def order_by(self, *_args):
                return self

            def iterator(self, *, chunk_size):
                return iter(self._rows)

        class FakeGroupModel:
            class objects:
                @staticmethod
                def values(*_args):
                    return FakeValuesQs(
                        [
                            {"id": 1, "name": "g1"},
                            {"id": 2, "name": "g2"},
                            {"id": 3, "name": "g3"},
                        ]
                    )

        group_cot = mock.Mock()
        group_cot.get_model.return_value = FakeGroupModel
        with mock.patch.object(
            object_report,
            "_group_membership_through",
            return_value=(FakeThrough, "group_id", "member_id"),
        ):
            result = object_report._check_empty_groups(group_cot, sample_limit=10)
        self.assertTrue(result["enabled"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(
            sorted(s["name"] for s in result["samples"]), ["g2", "g3"]
        )

    def test_check_single_member_groups_finds_singletons(self):
        class FakeAnnQs:
            def __init__(self, rows):
                self._rows = rows

            def annotate(self, **_kwargs):
                return self

            def filter(self, **_kwargs):
                return self

            def iterator(self, *, chunk_size):
                return iter(self._rows)

        class FakeThrough:
            class objects:
                @staticmethod
                def values(_field):
                    return FakeAnnQs([{"group_id": 5}, {"group_id": 6}])

        class FakeGroupQs:
            def __init__(self, rows):
                self._rows = rows

            def filter(self, pk__in):
                allowed = set(pk__in)
                return FakeGroupQs([r for r in self._rows if r["id"] in allowed])

            def values_list(self, *_args):
                return [(r["id"], r["name"]) for r in self._rows]

            def __iter__(self):
                for r in self._rows:
                    obj = mock.Mock()
                    obj.pk = r["id"]
                    obj.get_absolute_url.return_value = f"/g/{r['id']}/"
                    yield obj

        class FakeGroupModel:
            objects = FakeGroupQs([{"id": 5, "name": "s5"}, {"id": 6, "name": "s6"}])

        group_cot = mock.Mock()
        group_cot.get_model.return_value = FakeGroupModel
        with mock.patch.object(
            object_report,
            "_group_membership_through",
            return_value=(FakeThrough, "group_id", "member_id"),
        ):
            result = object_report._check_single_member_groups(
                group_cot, sample_limit=10
            )
        self.assertTrue(result["enabled"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(sorted(s["name"] for s in result["samples"]), ["s5", "s6"])

    def test_prepare_check_rows_orphans_detail(self):
        checks = {
            "ipam_orphans": {
                "enabled": True,
                "count": 3,
                "title": "Orphans",
                "literal_skipped": 4,
                "groups": [],
                "samples": [{"name": "x"}],
            },
        }
        rows = object_report.prepare_object_report_check_rows(checks)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "findings")
        self.assertTrue(
            any("literal-network" in d for d in rows[0]["details"]),
            rows[0]["details"],
        )

    def test_sample_limit_supports_pagination(self):
        # The stored cap must exceed the page size so the viewer can page.
        self.assertEqual(object_report.SAMPLE_PAGE_SIZE, 50)
        self.assertGreater(
            object_report.DEFAULT_SAMPLE_LIMIT, object_report.SAMPLE_PAGE_SIZE
        )

    def test_prepare_check_rows_carries_page_size(self):
        checks = {
            "ipam_duplicates": {
                "enabled": True,
                "count": 120,
                "title": "Dupes",
                "groups": [],
                "samples": [{"name": f"s{i}"} for i in range(120)],
            },
        }
        rows = object_report.prepare_object_report_check_rows(checks)
        self.assertEqual(rows[0]["sample_page_size"], object_report.SAMPLE_PAGE_SIZE)
        self.assertEqual(len(rows[0]["samples"]), 120)
        self.assertTrue(rows[0]["has_samples"])


class ObjectReportTomlExportTests(TestCase):
    def _sample_report(self):
        return {
            "available": True,
            "version": "1.2.3",
            "generated_at": "2026-01-01T00:00:00+00:00",
            "duration_s": 1.5,
            "sample_limit": 50,
            "findings_total": 4,
            "totals": {"addresses": 10, "ipam_linked": 8, "groups": 3},
            "checks": {
                "ipam_duplicates": {
                    "enabled": True,
                    "count": 2,
                    "excess_objects": 2,
                    "title": "Multiple address objects per IPAM resource",
                    "groups": [{"label": "ipaddress", "count": 2}],
                    "samples": [
                        {
                            "name": "1.2.3.4/32",
                            "url": "/ipam/ip/1/",
                            "ipam_type": "ipaddress",
                            "address_count": 2,
                        }
                    ],
                },
                "deprecated": {
                    "enabled": True,
                    "count": 0,
                    "title": "Deprecated objects",
                    "groups": [],
                    "samples": [],
                },
            },
        }

    def test_render_contains_structure(self):
        from netbox_nsm.object_report.toml_export import (
            OBJECT_REPORT_EXPORT_FORMAT,
            render_object_report_toml,
        )

        body = render_object_report_toml(self._sample_report())
        self.assertIn(f'format = "{OBJECT_REPORT_EXPORT_FORMAT}"', body)
        self.assertIn('plugin_version = "1.2.3"', body)
        self.assertIn("findings_total = 4", body)
        self.assertIn("[totals]", body)
        self.assertIn("addresses = 10", body)
        self.assertIn("[[checks]]", body)
        self.assertIn(
            'title = "Multiple address objects per IPAM resource"', body
        )
        self.assertIn("findings = 2", body)
        self.assertIn("excess_objects = 2", body)
        self.assertIn("[[checks.breakdown]]", body)
        self.assertIn('label = "ipaddress"', body)
        self.assertIn("[[checks.samples]]", body)
        self.assertIn('name = "1.2.3.4/32"', body)

    def test_render_is_valid_toml_when_parser_available(self):
        try:
            import tomllib
        except ImportError:  # Python < 3.11
            self.skipTest("tomllib not available")
        from netbox_nsm.object_report.toml_export import render_object_report_toml

        parsed = tomllib.loads(render_object_report_toml(self._sample_report()))
        self.assertEqual(parsed["format"], "netbox-nsm-object-report-v1")
        self.assertEqual(parsed["totals"]["addresses"], 10)
        self.assertEqual(len(parsed["checks"]), 2)
        dupes = next(c for c in parsed["checks"] if c["key"] == "ipam_duplicates")
        self.assertEqual(dupes["findings"], 2)
        self.assertEqual(dupes["breakdown"][0]["label"], "ipaddress")
        self.assertEqual(dupes["samples"][0]["name"], "1.2.3.4/32")

    def _all_checks_report(self):
        return {
            "available": True,
            "version": "2.0.0",
            "generated_at": "2026-02-02T00:00:00+00:00",
            "duration_s": 2.0,
            "sample_limit": 50,
            "findings_total": 12,
            "totals": {"addresses": 20, "ipam_linked": 15, "groups": 6},
            "checks": _all_checks_fixture(),
        }

    def test_render_contains_all_checks(self):
        from netbox_nsm.object_report.object_report import OBJECT_REPORT_CHECK_KEYS
        from netbox_nsm.object_report.toml_export import render_object_report_toml

        body = render_object_report_toml(self._all_checks_report())
        # Every check key is emitted, including the newer ones.
        for key in OBJECT_REPORT_CHECK_KEYS:
            self.assertIn(f'key = "{key}"', body)
        # ipam_orphans must carry its scalar ``literal_skipped`` metadata.
        self.assertIn("literal_skipped = 5", body)
        # Breakdown buckets and capped samples are serialized for the new checks.
        self.assertIn("[[checks.breakdown]]", body)
        self.assertIn("[[checks.samples]]", body)
        self.assertIn('name = "orphan-addr"', body)
        self.assertIn('name = "empty-grp"', body)
        self.assertIn('name = "single-grp"', body)

    def test_render_all_checks_parses_to_eight_entries(self):
        try:
            import tomllib
        except ImportError:  # Python < 3.11
            self.skipTest("tomllib not available")
        from netbox_nsm.object_report.object_report import OBJECT_REPORT_CHECK_KEYS
        from netbox_nsm.object_report.toml_export import render_object_report_toml

        parsed = tomllib.loads(render_object_report_toml(self._all_checks_report()))
        self.assertEqual(len(parsed["checks"]), len(OBJECT_REPORT_CHECK_KEYS))
        keys = {c["key"] for c in parsed["checks"]}
        self.assertEqual(keys, set(OBJECT_REPORT_CHECK_KEYS))
        orphans = next(c for c in parsed["checks"] if c["key"] == "ipam_orphans")
        self.assertEqual(orphans["literal_skipped"], 5)
        self.assertEqual(orphans["samples"][0]["name"], "orphan-addr")

    def test_render_unavailable_report(self):
        from netbox_nsm.object_report.toml_export import render_object_report_toml

        body = render_object_report_toml(
            {"available": False, "message": "Custom Object Type not deployed."}
        )
        self.assertIn("available = false", body)
        self.assertIn('message = "Custom Object Type not deployed."', body)


class ObjectReportJobTests(TestCase):
    def test_system_job_registered_daily(self):
        self.assertIn(ObjectReportJob, registry["system_jobs"])
        self.assertEqual(registry["system_jobs"][ObjectReportJob]["interval"], 1440)
        self.assertEqual(ObjectReportJob.name, OBJECT_REPORT_JOB_NAME)

    def test_run_persists_report_on_job_data(self):
        job = Job.objects.create(
            name=OBJECT_REPORT_JOB_NAME,
            status=JobStatusChoices.STATUS_RUNNING,
            job_id=uuid.uuid4(),
        )
        runner = ObjectReportJob(job)
        runner.run()
        job.refresh_from_db()
        self.assertTrue(isinstance(job.data, dict))
        self.assertIn("checks", job.data)

    def test_get_latest_returns_completed_with_data(self):
        Job.objects.create(
            name=OBJECT_REPORT_JOB_NAME,
            status=JobStatusChoices.STATUS_COMPLETED,
            job_id=uuid.uuid4(),
            completed=timezone.now(),
            data={"available": True, "findings_total": 1},
        )
        latest = get_latest_object_report_job()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.data["findings_total"], 1)

    def test_get_latest_finds_legacy_audit_job_name(self):
        from netbox_nsm.object_report.jobs import LEGACY_OBJECT_REPORT_JOB_NAMES

        legacy_name = LEGACY_OBJECT_REPORT_JOB_NAMES[0]
        Job.objects.create(
            name=legacy_name,
            status=JobStatusChoices.STATUS_COMPLETED,
            job_id=uuid.uuid4(),
            completed=timezone.now(),
            data={"available": True, "findings_total": 7},
        )
        latest = get_latest_object_report_job()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.data["findings_total"], 7)

    def test_get_pending_detects_enqueued(self):
        self.assertIsNone(get_pending_object_report_job())
        Job.objects.create(
            name=OBJECT_REPORT_JOB_NAME,
            status=JobStatusChoices.STATUS_PENDING,
            job_id=uuid.uuid4(),
        )
        self.assertIsNotNone(get_pending_object_report_job())

    def test_get_pending_ignores_scheduled_system_job(self):
        Job.objects.create(
            name=OBJECT_REPORT_JOB_NAME,
            status=JobStatusChoices.STATUS_SCHEDULED,
            job_id=uuid.uuid4(),
            interval=1440,
            scheduled=timezone.now() + timezone.timedelta(days=1),
        )
        self.assertIsNone(get_pending_object_report_job())

    def test_get_pending_detects_running(self):
        Job.objects.create(
            name=OBJECT_REPORT_JOB_NAME,
            status=JobStatusChoices.STATUS_RUNNING,
            job_id=uuid.uuid4(),
            started=timezone.now(),
        )
        self.assertIsNotNone(get_pending_object_report_job())

    @mock.patch("netbox_nsm.object_report.jobs._is_job_in_rq", return_value=False)
    def test_get_pending_finalizes_stale_job(self, _in_rq):
        stale = Job.objects.create(
            name=OBJECT_REPORT_JOB_NAME,
            status=JobStatusChoices.STATUS_RUNNING,
            job_id=uuid.uuid4(),
            started=timezone.now() - timezone.timedelta(hours=3),
        )
        self.assertIsNone(get_pending_object_report_job())
        stale.refresh_from_db()
        self.assertEqual(stale.status, JobStatusChoices.STATUS_ERRORED)
        self.assertIn("stale", stale.error.lower())


class ObjectReportViewTests(TestCase):
    def test_view_requires_permission(self):
        url = reverse("plugins:netbox_nsm:object_report")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_view_renders_without_report(self):
        grant_nsm_config_perms(self, view=True)
        url = reverse("plugins:netbox_nsm:object_report")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertContains(response, "Object Report")

    def test_view_renders_with_stored_report(self):
        grant_nsm_config_perms(self, view=True)
        Job.objects.create(
            name=OBJECT_REPORT_JOB_NAME,
            status=JobStatusChoices.STATUS_COMPLETED,
            job_id=uuid.uuid4(),
            completed=timezone.now(),
            data={
                "available": True,
                "findings_total": 3,
                "sample_limit": 50,
                "totals": {"addresses": 10, "ipam_linked": 8, "groups": 2},
                "checks": {
                    "status_mismatch": {
                        "enabled": True, "count": 0, "groups": [], "samples": [],
                        "title": "x", "explicit_config": True,
                        "checked": 8, "ignored": 0, "orphans": 0,
                    },
                    "ipam_duplicates": {
                        "enabled": True, "count": 3, "excess_objects": 3,
                        "groups": [{"label": "ipaddress", "count": 3}],
                        "samples": [{"name": "1.2.3.4", "url": "", "ipam_type": "ipaddress", "address_count": 2}],
                        "title": "dupes",
                    },
                    "multi_group": {
                        "enabled": True, "count": 0, "groups": [], "samples": [], "title": "mg",
                    },
                    "similar_groups": {
                        "enabled": True, "count": 0, "groups": [], "samples": [], "title": "sg",
                    },
                    "deprecated": {
                        "enabled": True, "count": 0, "groups": [], "samples": [], "title": "dep",
                    },
                },
            },
        )
        url = reverse("plugins:netbox_nsm:object_report")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertContains(response, "dupes")
        self.assertContains(response, "1.2.3.4")
        self.assertContains(response, 'class="table table-hover object-list')
        self.assertContains(response, "object-report-samples-ipam_duplicates")
        self.assertContains(response, "card-header")

    def test_view_renders_all_checks(self):
        grant_nsm_config_perms(self, view=True)
        Job.objects.create(
            name=OBJECT_REPORT_JOB_NAME,
            status=JobStatusChoices.STATUS_COMPLETED,
            job_id=uuid.uuid4(),
            completed=timezone.now(),
            data={
                "available": True,
                "findings_total": 12,
                "sample_limit": 50,
                "totals": {"addresses": 20, "ipam_linked": 15, "groups": 6},
                "checks": _all_checks_fixture(),
            },
        )
        url = reverse("plugins:netbox_nsm:object_report")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        content = response.content.decode()
        # All eight checks (including the newer orphan/empty/single-member ones)
        # are rendered with their title, sample block and sample rows.
        for key, sample_name in (
            ("status_mismatch", "addr-status"),
            ("ipam_duplicates", "10.0.0.1"),
            ("ipam_orphans", "orphan-addr"),
            ("multi_group", "multi-addr"),
            ("empty_groups", "empty-grp"),
            ("single_member_groups", "single-grp"),
            ("similar_groups", "grp-a"),
            ("deprecated", "dep-addr"),
        ):
            self.assertIn(f"object-report-samples-{key}", content)
            self.assertIn(sample_name, content)
        for title in (
            "all-ipam-orphans",
            "all-empty-groups",
            "all-single-member-groups",
        ):
            self.assertIn(title, content)

    def test_view_renders_sample_pager(self):
        grant_nsm_config_perms(self, view=True)
        samples = [
            {"name": f"1.2.3.{i}", "url": "", "ipam_type": "ipaddress"}
            for i in range(120)
        ]
        Job.objects.create(
            name=OBJECT_REPORT_JOB_NAME,
            status=JobStatusChoices.STATUS_COMPLETED,
            job_id=uuid.uuid4(),
            completed=timezone.now(),
            data={
                "available": True,
                "findings_total": 120,
                "sample_limit": 500,
                "totals": {"addresses": 200, "ipam_linked": 200, "groups": 0},
                "checks": {
                    "ipam_duplicates": {
                        "enabled": True,
                        "count": 120,
                        "excess_objects": 120,
                        "title": "dupes-pager",
                        "groups": [{"label": "ipaddress", "count": 120}],
                        "samples": samples,
                    },
                },
            },
        )
        url = reverse("plugins:netbox_nsm:object_report")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        content = response.content.decode()
        # All stored samples are rendered (paged client-side), pager controls
        # and the pagination JS asset are present.
        self.assertIn('class="nsm-or-samples"', content)
        self.assertIn('data-page-size="50"', content)
        self.assertIn('data-total-count="120"', content)
        self.assertIn("nsm-or-pager", content)
        self.assertIn("nsm-or-sample-row", content)
        self.assertIn('data-sample-index="119"', content)
        self.assertIn("object_report_samples.js", content)

    def test_export_toml_without_report_redirects(self):
        grant_nsm_config_perms(self, view=True)
        url = reverse("plugins:netbox_nsm:object_report")
        response = self.client.get(url, {"export": "toml"})
        self.assertEqual(response.status_code, 302)

    def test_export_toml_returns_document(self):
        grant_nsm_config_perms(self, view=True)
        Job.objects.create(
            name=OBJECT_REPORT_JOB_NAME,
            status=JobStatusChoices.STATUS_COMPLETED,
            job_id=uuid.uuid4(),
            completed=timezone.now(),
            data={
                "available": True,
                "version": "9.9.9",
                "findings_total": 1,
                "sample_limit": 50,
                "totals": {"addresses": 5, "ipam_linked": 4, "groups": 1},
                "checks": {
                    "ipam_duplicates": {
                        "enabled": True,
                        "count": 1,
                        "excess_objects": 1,
                        "title": "dupes-export",
                        "groups": [{"label": "ipaddress", "count": 1}],
                        "samples": [
                            {"name": "9.9.9.9", "url": "", "ipam_type": "ipaddress"}
                        ],
                    },
                },
            },
        )
        url = reverse("plugins:netbox_nsm:object_report")
        response = self.client.get(url, {"export": "toml"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("application/toml"))
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(".toml", response["Content-Disposition"])
        content = response.content.decode()
        self.assertIn("netbox-nsm-object-report-v1", content)
        self.assertIn("dupes-export", content)
        self.assertIn("9.9.9.9", content)

    def test_export_toml_requires_permission(self):
        url = reverse("plugins:netbox_nsm:object_report")
        response = self.client.get(url, {"export": "toml"})
        self.assertEqual(response.status_code, 403)

    @mock.patch(
        "netbox_nsm.views.object_report._count_active_rq_workers", return_value=0
    )
    def test_run_without_worker_errors(self, _workers):
        grant_nsm_config_perms(self, view=True)
        url = reverse("plugins:netbox_nsm:object_report")
        response = self.client.post(url, {"action": "run"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no RQ worker")

    @mock.patch("netbox_nsm.object_report.jobs.ObjectReportJob.enqueue")
    @mock.patch(
        "netbox_nsm.views.object_report._count_active_rq_workers", return_value=1
    )
    def test_run_enqueues_with_worker(self, _workers, mock_enqueue):
        mock_enqueue.return_value = mock.Mock(pk=99)
        grant_nsm_config_perms(self, view=True)
        url = reverse("plugins:netbox_nsm:object_report")
        response = self.client.post(url, {"action": "run"}, follow=True)
        self.assertEqual(response.status_code, 200)
        mock_enqueue.assert_called_once()

    def test_view_hides_progress_for_scheduled_system_job(self):
        grant_nsm_config_perms(self, view=True)
        Job.objects.create(
            name=OBJECT_REPORT_JOB_NAME,
            status=JobStatusChoices.STATUS_COMPLETED,
            job_id=uuid.uuid4(),
            completed=timezone.now(),
            data={"available": True, "findings_total": 0, "totals": {}, "checks": {}},
        )
        Job.objects.create(
            name=OBJECT_REPORT_JOB_NAME,
            status=JobStatusChoices.STATUS_SCHEDULED,
            job_id=uuid.uuid4(),
            interval=1440,
            scheduled=timezone.now() + timezone.timedelta(days=1),
        )
        url = reverse("plugins:netbox_nsm:object_report")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotContains(response, "Run in progress")
        self.assertContains(response, "Run now")

    def test_view_sort_findings_query_param(self):
        grant_nsm_config_perms(self, view=True)
        Job.objects.create(
            name=OBJECT_REPORT_JOB_NAME,
            status=JobStatusChoices.STATUS_COMPLETED,
            job_id=uuid.uuid4(),
            completed=timezone.now(),
            data={
                "available": True,
                "findings_total": 4,
                "sample_limit": 50,
                "totals": {"addresses": 1, "ipam_linked": 1, "groups": 0},
                "checks": {
                    "status_mismatch": {
                        "enabled": True, "count": 1, "groups": [], "samples": [],
                        "title": "first",
                    },
                    "ipam_duplicates": {
                        "enabled": True, "count": 3, "groups": [], "samples": [],
                        "title": "second",
                    },
                    "multi_group": {
                        "enabled": True, "count": 0, "groups": [], "samples": [],
                        "title": "third",
                    },
                    "similar_groups": {
                        "enabled": True, "count": 0, "groups": [], "samples": [],
                        "title": "fifth",
                    },
                    "deprecated": {
                        "enabled": True, "count": 0, "groups": [], "samples": [],
                        "title": "fourth",
                    },
                },
            },
        )
        url = reverse("plugins:netbox_nsm:object_report")
        response = self.client.get(url, {"sort": "-findings"})
        self.assertEqual(response.status_code, 200, response.content)
        content = response.content.decode()
        pos_second = content.index("second")
        pos_first = content.index("first")
        self.assertLess(pos_second, pos_first)


class BuildObjectReportIntegrationTests(TestCase):
    """End-to-end assembly of ``build_object_report()`` with the COT data layer
    mocked out.

    The individual ``_check_*`` helpers (and their through-table interactions)
    are unit-tested above against fake querysets; this test verifies that the
    public entry point wires the address/group COTs, totals and *all* eight
    checks into one JSON-serializable report dict (rather than the
    ``unavailable``/no-COT short-circuit)."""

    def test_build_object_report_assembles_all_checks(self):
        addr_model = mock.Mock(name="FakeAddressModel")
        addr_model.objects.count.return_value = 20
        addr_model.objects.exclude.return_value.count.return_value = 15
        addr_cot = mock.Mock(name="FakeAddressCOT")
        addr_cot.get_model.return_value = addr_model

        group_model = mock.Mock(name="FakeGroupModel")
        group_model.objects.count.return_value = 6
        group_cot = mock.Mock(name="FakeGroupCOT")
        group_cot.get_model.return_value = group_model

        fake_checks = _all_checks_fixture()

        def _stub(key):
            return lambda *args, **kwargs: fake_checks[key]

        patches = {
            "_address_cot": mock.patch.object(
                object_report, "_address_cot", return_value=addr_cot
            ),
            "_group_cot": mock.patch.object(
                object_report, "_group_cot", return_value=group_cot
            ),
            "_builder_status_map": mock.patch.object(
                object_report, "_builder_status_map", return_value=({}, False)
            ),
            "_check_status_mismatch": mock.patch.object(
                object_report, "_check_status_mismatch", _stub("status_mismatch")
            ),
            "_check_ipam_duplicates": mock.patch.object(
                object_report, "_check_ipam_duplicates", _stub("ipam_duplicates")
            ),
            "_check_ipam_orphans": mock.patch.object(
                object_report, "_check_ipam_orphans", _stub("ipam_orphans")
            ),
            "_check_multi_group": mock.patch.object(
                object_report, "_check_multi_group", _stub("multi_group")
            ),
            "_check_empty_groups": mock.patch.object(
                object_report, "_check_empty_groups", _stub("empty_groups")
            ),
            "_check_single_member_groups": mock.patch.object(
                object_report,
                "_check_single_member_groups",
                _stub("single_member_groups"),
            ),
            "_check_similar_groups": mock.patch.object(
                object_report, "_check_similar_groups", _stub("similar_groups")
            ),
            "_check_deprecated": mock.patch.object(
                object_report, "_check_deprecated", _stub("deprecated")
            ),
        }
        started = [p.start() for p in patches.values()]
        try:
            report = object_report.build_object_report(
                sample_limit=50, chunk_size=100
            )
        finally:
            for p in patches.values():
                p.stop()
        del started

        self.assertTrue(report["available"])
        self.assertEqual(
            set(report["checks"].keys()),
            set(object_report.OBJECT_REPORT_CHECK_KEYS),
        )
        self.assertEqual(
            report["totals"], {"addresses": 20, "ipam_linked": 15, "groups": 6}
        )
        # findings_total is the sum of all eight check counts (2+1+3+1+2+1+1+1).
        self.assertEqual(report["findings_total"], 12)
        for field in ("generated_at", "version", "duration_s"):
            self.assertIn(field, report)
        self.assertEqual(report["sample_limit"], 50)
        # The newer checks carry their structured payload through unchanged.
        self.assertEqual(report["checks"]["ipam_orphans"]["literal_skipped"], 5)
        self.assertEqual(report["checks"]["empty_groups"]["count"], 2)
        self.assertEqual(
            report["checks"]["single_member_groups"]["count"], 1
        )

    def test_build_object_report_unavailable_without_address_cot(self):
        with mock.patch.object(object_report, "_address_cot", return_value=None):
            report = object_report.build_object_report()
        self.assertFalse(report["available"])
        self.assertEqual(report["checks"], {})
