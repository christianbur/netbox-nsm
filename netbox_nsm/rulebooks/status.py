"""Rulebook status display helpers."""

from __future__ import annotations

from django.db import models
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

__all__ = (
    "RULEBOOK_STATUS_BADGE_CLASS",
    "RulebookStatusChoices",
    "rulebook_status_badge_html",
)


class RulebookStatusChoices(models.TextChoices):
    ACTIVE = "active", _("Active")
    DEPRECATED = "deprecated", _("Deprecated")
    RESERVED = "reserved", _("Reserved")
    CONTAINER = "container", _("Container")


RULEBOOK_STATUS_BADGE_CLASS: dict[str, str] = {
    RulebookStatusChoices.ACTIVE: "text-bg-success",
    RulebookStatusChoices.DEPRECATED: "text-bg-warning",
    RulebookStatusChoices.RESERVED: "text-bg-info",
    RulebookStatusChoices.CONTAINER: "text-bg-secondary",
}


def rulebook_status_badge_html(status: str, *, label: str | None = None) -> str:
    css = RULEBOOK_STATUS_BADGE_CLASS.get(status, "text-bg-secondary")
    text = label
    if text is None:
        try:
            text = str(RulebookStatusChoices(status).label)
        except ValueError:
            text = status or str(_("Unknown"))
    return format_html(
        '<span class="badge {}">{}</span>',
        css,
        text,
    )
