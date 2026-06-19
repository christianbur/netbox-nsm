"""Serialize a stored object report into a structured TOML document.

The export is intentionally **server-side** and works off the persisted report
payload (``Job.data``) rather than scraping the rendered DOM:

* the report is already a structured dict (counts + grouped breakdowns + capped
  detail samples), so a server-side serializer reproduces *all* of it — including
  breakdown buckets and the structured sample metadata that the collapsible
  sample rows render — without re-running any analysis;
* TOML keeps the format consistent with the rulebook rules export
  (``rulebook_rules_chrome.js``), which the user explicitly asked to be TOML.

A tiny hand-rolled writer is used (mirroring the JS escaping conventions) so the
plugin does not depend on a third-party TOML writer being installed.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from django.utils import timezone

from netbox_nsm.object_report.object_report import OBJECT_REPORT_CHECK_KEYS

__all__ = (
    "OBJECT_REPORT_EXPORT_FORMAT",
    "render_object_report_toml",
)

OBJECT_REPORT_EXPORT_FORMAT = "netbox-nsm-object-report-v1"

# Check-level keys that are rendered explicitly (or as nested arrays) and must
# not be emitted again as generic scalar metadata.
_CHECK_RESERVED_KEYS = frozenset(
    {"title", "enabled", "count", "groups", "samples"}
)

_BARE_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _toml_string(value: Any) -> str:
    text = "" if value is None else str(value)
    text = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f'"{text}"'


def _toml_key(value: Any) -> str:
    text = "" if value is None else str(value)
    if _BARE_KEY_RE.match(text):
        return text
    return _toml_string(text)


def _toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        # Guard against non-finite values that are not valid TOML.
        if value != value or value in (float("inf"), float("-inf")):
            return _toml_string(value)
        return repr(value)
    return _toml_string(value)


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _emit_scalar_items(lines: list[str], data: dict, *, skip: Iterable[str] = ()) -> None:
    skip_set = set(skip)
    for key in sorted(data):
        if key in skip_set:
            continue
        value = data[key]
        if value is None or not _is_scalar(value):
            continue
        lines.append(f"{_toml_key(key)} = {_toml_scalar(value)}")


def _emit_table_array(lines: list[str], header: str, rows: list[dict]) -> None:
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(f"[[{header}]]")
        _emit_scalar_items(lines, row)
        lines.append("")


def render_object_report_toml(report: dict[str, Any] | None, *, exported_at: str | None = None) -> str:
    """Return a TOML document describing every check, breakdown and sample."""
    report = report or {}
    available = bool(report.get("available"))
    exported_at = exported_at or timezone.now().isoformat()

    lines: list[str] = [
        f"format = {_toml_string(OBJECT_REPORT_EXPORT_FORMAT)}",
    ]
    if report.get("version"):
        lines.append(f"plugin_version = {_toml_string(report['version'])}")
    if report.get("generated_at"):
        lines.append(f"generated_at = {_toml_string(report['generated_at'])}")
    lines.append(f"exported_at = {_toml_string(exported_at)}")
    lines.append(f"available = {_toml_scalar(available)}")
    if report.get("duration_s") is not None:
        lines.append(f"duration_s = {_toml_scalar(float(report['duration_s']))}")
    if report.get("sample_limit"):
        lines.append(f"sample_limit = {_toml_scalar(int(report['sample_limit']))}")
    lines.append(f"findings_total = {_toml_scalar(int(report.get('findings_total') or 0))}")
    if not available and report.get("message"):
        lines.append(f"message = {_toml_string(report['message'])}")
    lines.append("")

    totals = report.get("totals") or {}
    if isinstance(totals, dict) and totals:
        lines.append("[totals]")
        _emit_scalar_items(lines, totals)
        lines.append("")

    checks = report.get("checks") or {}
    if isinstance(checks, dict) and checks:
        ordered_keys = [k for k in OBJECT_REPORT_CHECK_KEYS if k in checks]
        ordered_keys += [k for k in checks if k not in ordered_keys]
        for key in ordered_keys:
            data = checks.get(key)
            if not isinstance(data, dict):
                continue
            lines.append("[[checks]]")
            lines.append(f"key = {_toml_string(key)}")
            lines.append(f"title = {_toml_string(data.get('title', key))}")
            lines.append(f"enabled = {_toml_scalar(bool(data.get('enabled', True)))}")
            lines.append(f"findings = {_toml_scalar(int(data.get('count') or 0))}")
            _emit_scalar_items(lines, data, skip=_CHECK_RESERVED_KEYS)
            lines.append("")
            groups = data.get("groups") or []
            if isinstance(groups, list) and groups:
                _emit_table_array(lines, "checks.breakdown", groups)
            samples = data.get("samples") or []
            if isinstance(samples, list) and samples:
                _emit_table_array(lines, "checks.samples", samples)

    return "\n".join(lines).rstrip("\n") + "\n"
