from __future__ import annotations

import re

from django.utils.html import escape
from django.utils.translation import gettext as _

from netbox_nsm.rulebooks.cell_html import rules_filter_target_html

def enabled_status_labels() -> dict[str, str]:
    """Translated On/Off labels for rules table status cells."""
    return {"on": _("On"), "off": _("Off")}


def _enabled_filter_text(enabled: bool) -> str:
    """Search tokens for rules table text filter (locale label + DE/EN synonyms)."""
    labels = enabled_status_labels()
    if enabled:
        return f"{labels['on']} on enabled aktiv ein 1"
    return f"{labels['off']} off disabled inaktiv aus 0"


def _description_cell_html(system: dict) -> str:
    desc = system.get("description") or ""
    if desc == "-":
        desc = ""
    if not desc:
        return '<span class="nsm-cell-empty">-</span>'
    parts = re.split(r"\s→\s", desc)
    if len(parts) >= 2:
        lines = "".join(
            rules_filter_target_html(
                f'<span class="nsm-ag-description-part">{escape(part.strip())}</span>',
                part.strip(),
            )
            for part in parts
            if part.strip()
        )
        return f'<div class="nsm-ag-description-lines">{lines}</div>'
    return rules_filter_target_html(
        f'<span class="nsm-ag-description-text">{escape(desc)}</span>',
        desc,
    )


def _description_line_count(desc_raw: str) -> int:
    text = (desc_raw or "").strip()
    if not text or text == "-":
        return 0
    parts = re.split(r"\s→\s", text)
    return len(parts) if len(parts) >= 2 else 1

