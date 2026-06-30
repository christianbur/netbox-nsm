"""Label analyzer (Phase E skeleton) — see ``capability.py``."""

from netbox_nsm.analyzers.label.capability import (
    LABEL_ANALYZER_KEY,
    build_label_analysis,
    iter_label_cots,
    label_analyzer_spec,
)

__all__ = (
    "LABEL_ANALYZER_KEY",
    "build_label_analysis",
    "iter_label_cots",
    "label_analyzer_spec",
)
