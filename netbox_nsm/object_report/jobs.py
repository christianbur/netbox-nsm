"""Scheduled execution wrapper for the NSM object report.

Uses NetBox's native background-job framework (NetBox 4.5/4.6):

* ``@system_job(interval=...)`` registers ``ObjectReportJob`` in
  ``registry['system_jobs']``. At RQ-worker startup, NetBox's ``rqworker``
  command calls ``enqueue_once()`` for every registered system job, which
  schedules the recurring run idempotently. ``JobRunner.handle()`` then
  re-schedules the next run after each execution using the ``interval``.
* The report payload is persisted on ``Job.data`` (JSONField) so the last run
  can be displayed without recomputation. No extra model/migration is required;
  retention follows NetBox's normal ``Job`` housekeeping.

Manual runs use ``ObjectReportJob.enqueue(...)`` (immediate), which is independent
of the recurring schedule.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.choices import JobIntervalChoices, JobStatusChoices
from netbox.jobs import JobRunner, system_job

from netbox_nsm.object_report.object_report import build_object_report

__all__ = (
    "ObjectReportJob",
    "OBJECT_REPORT_JOB_NAME",
    "LEGACY_OBJECT_REPORT_JOB_NAMES",
    "object_report_job_names",
    "get_latest_object_report_job",
    "get_pending_object_report_job",
)

OBJECT_REPORT_JOB_NAME = "NSM Object Report"
LEGACY_OBJECT_REPORT_JOB_NAMES = ("NSM Audit Report",)

# Only immediate queue states count as "in progress" for the UI. ``scheduled``
# is the idempotent successor created after each daily system run and must not
# block manual "Run now".
_ACTIVE_OBJECT_REPORT_STATUSES = (
    JobStatusChoices.STATUS_PENDING,
    JobStatusChoices.STATUS_RUNNING,
)

# Jobs stuck in pending/running longer than this with no RQ entry are treated as stale.
_STALE_OBJECT_REPORT_JOB_AGE = timedelta(hours=2)


def object_report_job_names():
    """Return all ``Job.name`` values that identify an object report run."""
    return (OBJECT_REPORT_JOB_NAME, *LEGACY_OBJECT_REPORT_JOB_NAMES)


@system_job(interval=JobIntervalChoices.INTERVAL_DAILY)
class ObjectReportJob(JobRunner):
    """Daily background job that builds and stores the NSM object report."""

    class Meta:
        name = OBJECT_REPORT_JOB_NAME

    def run(self, *args, **kwargs):
        report = build_object_report()
        # Persist the aggregated payload on the Job so the viewer can render the
        # last run without recomputation. ``handle()`` saves again on terminate;
        # the instance attribute is preserved.
        self.job.data = report
        self.job.save(update_fields=["data"])
        self.logger.info(
            "Object report complete: %s finding(s) across %s address object(s)."
            % (
                report.get("findings_total", 0),
                (report.get("totals") or {}).get("addresses", 0),
            )
        )


def get_latest_object_report_job():
    """Return the most recent completed ``ObjectReportJob`` with a stored report."""
    from core.models import Job

    return (
        Job.objects.filter(
            name__in=object_report_job_names(),
            status=JobStatusChoices.STATUS_COMPLETED,
        )
        .exclude(data__isnull=True)
        .order_by("-completed")
        .first()
    )


def _is_job_in_rq(job) -> bool:
    """Return True if the NetBox job still has a corresponding RQ job."""
    try:
        import django_rq
        from rq.job import Job as RQJob

        queue = django_rq.get_queue(job.queue_name or "default")
        rq_job = RQJob.fetch(str(job.job_id), connection=queue.connection)
        return rq_job.get_status() in {"queued", "scheduled", "started", "deferred"}
    except Exception:
        return False


def _finalize_stale_object_report_job(job):
    """Mark a DB job that is no longer in RQ as errored."""
    job.status = JobStatusChoices.STATUS_ERRORED
    job.error = str(_("Job lost from queue (stale)."))
    job.completed = timezone.now()
    job.save(update_fields=["status", "error", "completed"])


def get_pending_object_report_job():
    """Return a currently pending/running ``ObjectReportJob``, if any.

    Excludes ``scheduled`` rows: those are the next daily system occurrence
    created by ``JobRunner.handle()`` and are not an active manual run.
    """
    from core.models import Job

    job = (
        Job.objects.filter(
            name__in=object_report_job_names(),
            status__in=_ACTIVE_OBJECT_REPORT_STATUSES,
        )
        .order_by("-created")
        .first()
    )
    if job is None:
        return None

    reference_time = job.started or job.created
    if timezone.now() - reference_time > _STALE_OBJECT_REPORT_JOB_AGE:
        if not _is_job_in_rq(job):
            _finalize_stale_object_report_job(job)
            return None

    return job
