"""Label analyzer capability (Phase E skeleton).

The label analyzer inspects ``label``-role COTs (classification labels) and how
they are referenced by rulebooks. This is a minimal scaffold: it registers the
``analyzer.label`` capability and exposes a structural summary so the platform
can advertise the analyzer before the full UI lands.
"""

from __future__ import annotations

from netbox_nsm.analyzers.registry import get_analyzer

__all__ = (
    "LABEL_ANALYZER_KEY",
    "label_analyzer_spec",
    "iter_label_cots",
    "build_label_analysis",
)

LABEL_ANALYZER_KEY = "label"


def label_analyzer_spec():
    """Return the registered ``AnalyzerSpec`` for the label analyzer."""
    return get_analyzer(LABEL_ANALYZER_KEY)


def iter_label_cots():
    """Yield deployed COTs whose resolved role is ``label`` (cot_roles)."""
    from netbox_nsm.objects.cot_roles import iter_cots_by_role

    yield from iter_cots_by_role("label")


def build_label_analysis() -> dict:
    """Skeleton analysis payload: which label COTs are deployed.

    Reserved for the full label analyzer; returns a structural, role-driven
    summary today so callers and tests can rely on a stable shape.
    """
    spec = label_analyzer_spec()
    cots = list(iter_label_cots())
    return {
        "available": bool(cots),
        "capability": getattr(spec, "capability", "analyzer.label"),
        "run_mode": getattr(spec, "run_mode", "planned"),
        "label_cots": [getattr(cot, "slug", "") for cot in cots],
    }
