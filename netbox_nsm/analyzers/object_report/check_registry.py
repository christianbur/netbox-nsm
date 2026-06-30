"""Extensible custom checks for the Object Report (Phase E).

Built-in checks live in ``object_report.py``. Third parties (or downstream
bundles) can contribute extra checks without patching core by registering a
callable here. Each check receives an ``ObjectReportContext`` and returns the
same result dict shape as the built-in checks (``enabled``, ``count``,
``groups``, ``samples``, ``title``, ...).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

__all__ = (
    "ObjectReportContext",
    "register_object_report_check",
    "unregister_object_report_check",
    "iter_object_report_checks",
    "clear_object_report_checks",
    "run_extra_object_report_checks",
)


@dataclass(frozen=True)
class ObjectReportContext:
    """Read-only inputs handed to a custom object-report check."""

    addr_cot: Any
    addr_model: Any
    group_cot: Any
    sample_limit: int
    chunk_size: int


# key -> callable(ObjectReportContext) -> dict
_CHECKS: dict[str, Callable[[ObjectReportContext], dict]] = {}


def register_object_report_check(
    key: str, fn: Callable[[ObjectReportContext], dict]
) -> None:
    """Register a custom check under *key* (overwrites an existing same key)."""
    _CHECKS[key] = fn


def unregister_object_report_check(key: str) -> None:
    _CHECKS.pop(key, None)


def clear_object_report_checks() -> None:
    _CHECKS.clear()


def iter_object_report_checks():
    """Yield ``(key, fn)`` for every registered custom check."""
    return list(_CHECKS.items())


def run_extra_object_report_checks(context: ObjectReportContext) -> dict[str, dict]:
    """Run all registered custom checks, returning ``{key: result_dict}``.

    A failing check is isolated (recorded as disabled) so one bad extension can
    never break the whole report.
    """
    results: dict[str, dict] = {}
    for key, fn in iter_object_report_checks():
        try:
            result = fn(context)
        except Exception as exc:  # noqa: BLE001 — isolate third-party failures
            result = {
                "enabled": False,
                "count": 0,
                "groups": [],
                "samples": [],
                "note": f"Custom check failed: {exc}",
                "title": key,
            }
        if isinstance(result, dict):
            results[key] = result
    return results
