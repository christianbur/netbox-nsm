"""IP analyzer capability registration."""

from __future__ import annotations

from netbox_nsm.analyzers.registry import get_analyzer

__all__ = (
    "IP_ANALYZER_KEY",
    "ip_analyzer_spec",
)

IP_ANALYZER_KEY = "ip_analyzer"


def ip_analyzer_spec():
    """Return the registered ``AnalyzerSpec`` for the IP analyzer."""
    return get_analyzer(IP_ANALYZER_KEY)
