"""Capability registry for NSM analyzer UIs.

Single source of truth that maps each analyzer to its capability key, URL name,
and run mode. UI entry points (Object Analyzer link, IP analysis applet, Object
Report) resolve their URLs through this registry instead of hardcoding url names.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    "AnalyzerSpec",
    "ANALYZER_REGISTRY",
    "ANALYZER_BY_KEY",
    "get_analyzer",
    "analyzer_url_name",
    "analyzer_reverse",
    "iter_analyzers",
)


@dataclass(frozen=True, slots=True)
class AnalyzerSpec:
    key: str
    capability: str
    url_name: str
    label: str
    run_mode: str = "page"


ANALYZER_REGISTRY: tuple[AnalyzerSpec, ...] = (
    AnalyzerSpec("object_analyzer", "analyzer.object_analyzer", "object_analyzer", "Object Analyzer"),
    AnalyzerSpec(
        "ip_analyzer",
        "analyzer.ip_analyzer",
        "ip_analysis_api",
        "IP Analyzer",
        run_mode="applet",
    ),
    AnalyzerSpec("object_report", "analyzer.object_report", "object_report", "Object Report", run_mode="job"),
    # Phase E skeleton — not yet routed (url_name empty, run_mode "planned").
    AnalyzerSpec("label", "analyzer.label", "", "Label Analyzer", run_mode="planned"),
)

ANALYZER_BY_KEY: dict[str, AnalyzerSpec] = {spec.key: spec for spec in ANALYZER_REGISTRY}


def get_analyzer(key: str) -> AnalyzerSpec | None:
    return ANALYZER_BY_KEY.get(key)


def analyzer_url_name(key: str) -> str:
    """Return the plugin URL name for analyzer *key* (raises ``KeyError`` if unknown)."""
    return ANALYZER_BY_KEY[key].url_name


def analyzer_reverse(key: str, **kwargs) -> str:
    """Reverse the plugin URL for analyzer *key*."""
    from django.urls import reverse

    return reverse(f"plugins:netbox_nsm:{analyzer_url_name(key)}", kwargs=kwargs or None)


def iter_analyzers():
    """Iterate the registered analyzer specs."""
    return iter(ANALYZER_REGISTRY)
