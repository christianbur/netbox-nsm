"""django-tables2 table for the Object Report checks list."""

from __future__ import annotations

import django_tables2 as tables
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

__all__ = ("ObjectReportCheckTable",)


class _FindingsColumn(tables.Column):
    def render(self, value, record):
        if not record["enabled"]:
            return format_html(
                '<span class="badge bg-secondary-subtle text-secondary">{}</span>',
                _("n/a"),
            )
        if value:
            css = "bg-warning-subtle text-warning"
        else:
            css = "bg-success-subtle text-success"
        return format_html('<span class="badge {}">{}</span>', css, value)


class _StatusColumn(tables.Column):
    def render(self, value, record):
        status = record["status"]
        if status == "ok":
            css = "bg-success-subtle text-success"
        elif status == "findings":
            css = "bg-warning-subtle text-warning"
        else:
            css = "bg-secondary-subtle text-secondary"
        return format_html(
            '<span class="badge {}">{}</span>',
            css,
            record["status_label"],
        )


class _DetailsColumn(tables.Column):
    def render(self, value, record):
        details = record.get("details") or []
        if details:
            parts = [
                format_html('<div{}>{}</div>', mark_safe(' class="mt-1"' if idx else ""), line)
                for idx, line in enumerate(details)
            ]
            return mark_safe("".join(parts))
        if record["enabled"] and record["count"] == 0:
            return format_html(
                '<span class="text-success"><i class="mdi mdi-check-circle"></i> {}</span>',
                _("No findings."),
            )
        return mark_safe('<span class="text-muted">—</span>')


class _BreakdownColumn(tables.Column):
    def render(self, value, record):
        groups = record.get("groups") or []
        if not groups:
            return mark_safe('<span class="text-muted">—</span>')
        items = [
            format_html(
                '<li><span class="text-muted">{}</span> '
                '<span class="badge bg-secondary-subtle text-secondary">{}</span></li>',
                g["label"],
                g["count"],
            )
            for g in groups
        ]
        return format_html('<ul class="list-unstyled mb-0">{}</ul>', mark_safe("".join(items)))


class _SamplesColumn(tables.Column):
    def render(self, value, record):
        if record["has_samples"]:
            shown = len(record["samples"])
            total = record["count"]
            label = _("%(shown)s of %(total)s") % {"shown": shown, "total": total}
            return format_html(
                '<button type="button" class="btn btn-sm btn-ghost-secondary"'
                ' data-bs-toggle="collapse"'
                ' data-bs-target="#object-report-samples-{}"'
                ' aria-expanded="false"'
                ' aria-controls="object-report-samples-{}"'
                '><i class="mdi mdi-unfold-more-horizontal"></i> {}</button>',
                record["key"],
                record["key"],
                label,
            )
        return mark_safe('<span class="text-muted">—</span>')


class ObjectReportCheckTable(tables.Table):
    """NetBox-style object-list table for aggregated object-report checks."""

    title = tables.Column(
        verbose_name=_("Check"),
        orderable=False,
        attrs={"td": {"class": "fw-semibold"}},
    )
    findings = _FindingsColumn(
        accessor="count",
        verbose_name=_("Findings"),
        orderable=True,
        attrs={
            "th": {"class": "text-end"},
            "td": {"class": "text-end"},
        },
    )
    status = _StatusColumn(
        accessor="status",
        verbose_name=_("Status"),
        orderable=False,
    )
    details = _DetailsColumn(
        accessor="details",
        verbose_name=_("Details"),
        orderable=False,
        attrs={"td": {"class": "small"}},
    )
    breakdown = _BreakdownColumn(
        accessor="groups",
        verbose_name=_("Breakdown"),
        orderable=False,
        attrs={"td": {"class": "small"}},
    )
    samples = _SamplesColumn(
        verbose_name=_("Samples"),
        orderable=False,
        empty_values=(),
        attrs={
            "th": {"class": "text-end"},
            "td": {"class": "text-end text-nowrap"},
        },
    )

    class Meta:
        attrs = {"class": "table table-hover object-list mb-0"}
        fields = ("title", "findings", "status", "details", "breakdown", "samples")
        order_by = ("title",)
        empty_text = _("No checks available.")
