"""Object Report viewer: show the last run and trigger a new background run."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django_tables2 import RequestConfig

from netbox_nsm.type_metadata.permissions import VIEW_CUSTOM_OBJECT_TYPE

__all__ = ("ObjectReportView",)


def _count_active_rq_workers() -> int:
    try:
        import django_rq
        from rq.worker import Worker

        conn = django_rq.get_connection()
        return len(Worker.all(connection=conn))
    except Exception:
        return 0


class ObjectReportView(LoginRequiredMixin, View):
    template_name = "netbox_nsm/object_report.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.has_perm(VIEW_CUSTOM_OBJECT_TYPE):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

    def _context(self, request):
        from netbox_nsm.analyzers.object_report.object_report import (
            localize_object_report,
            prepare_object_report_check_rows,
        )
        from netbox_nsm.analyzers.object_report.jobs import (
            get_latest_object_report_job,
            get_pending_object_report_job,
        )

        latest = get_latest_object_report_job()
        pending = get_pending_object_report_job()
        report = latest.data if latest is not None else None
        if report is not None:
            report = localize_object_report(report)

        check_rows = []
        table = None
        if report and report.get("checks"):
            check_rows = prepare_object_report_check_rows(
                report["checks"],
                sample_limit=report.get("sample_limit") or 50,
            )
            from netbox_nsm.analyzers.object_report.tables import ObjectReportCheckTable

            table = ObjectReportCheckTable(check_rows)
            RequestConfig(request, paginate=False).configure(table)

        return {
            "latest_job": latest,
            "pending_job": pending,
            "report": report,
            "check_rows": check_rows,
            "table": table,
            "generated_at": getattr(latest, "completed", None),
            "run_by": getattr(latest, "user", None),
        }

    def get(self, request):
        if request.GET.get("export") == "toml":
            return self._export_toml(request)
        return render(request, self.template_name, self._context(request))

    def _export_toml(self, request):
        from netbox_nsm.analyzers.object_report.jobs import get_latest_object_report_job
        from netbox_nsm.analyzers.object_report.object_report import localize_object_report
        from netbox_nsm.analyzers.object_report.toml_export import render_object_report_toml

        latest = get_latest_object_report_job()
        report = latest.data if latest is not None else None
        if not report:
            messages.warning(
                request, _("No object report available to export yet.")
            )
            return redirect(reverse("plugins:netbox_nsm:object_report"))

        report = localize_object_report(report)
        body = render_object_report_toml(report)

        stamp_source = getattr(latest, "completed", None) or timezone.now()
        stamp = timezone.localtime(stamp_source).strftime("%Y-%m-%dT%H-%M-%S")
        filename = f"nsm_object_report_{stamp}.toml"

        response = HttpResponse(body, content_type="application/toml; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def post(self, request):
        if request.POST.get("action") != "run":
            return redirect(reverse("plugins:netbox_nsm:object_report"))

        from netbox_nsm.analyzers.object_report.jobs import (
            ObjectReportJob,
            get_pending_object_report_job,
        )

        pending = get_pending_object_report_job()
        if pending is not None:
            messages.info(
                request,
                _("An object report run is already queued or running (job %(id)s).")
                % {"id": pending.pk},
            )
            return redirect(reverse("plugins:netbox_nsm:object_report"))

        if _count_active_rq_workers() < 1:
            messages.error(
                request,
                _(
                    "Object report could not be queued: no RQ worker is running. "
                    "Start the NetBox RQ worker and try again."
                ),
            )
            return redirect(reverse("plugins:netbox_nsm:object_report"))

        job = ObjectReportJob.enqueue(user=request.user)
        messages.success(
            request,
            _("Object report started in the background (job %(id)s).")
            % {"id": job.pk},
        )
        return redirect(reverse("plugins:netbox_nsm:object_report"))
