"""Capability registry for NSM analyzer UIs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnalyzerSpec:
    key: str
    capability: str
    url_name: str
    label: str
    run_mode: str = "page"


ANALYZER_REGISTRY: tuple[AnalyzerSpec, ...] = (
    AnalyzerSpec("object_analyzer", "analyzer.object_analyzer", "object_analyzer", "Object Analyzer"),
    AnalyzerSpec("ip", "analyzer.ip", "ip_analysis_api", "IP Analysis", run_mode="applet"),
    AnalyzerSpec("object_report", "analyzer.object_report", "object_report", "Object Report", run_mode="job"),
)
