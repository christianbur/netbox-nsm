"""Object Analyzer — graph edge registry and resolvers.

``analysis.analyzer`` builds the interactive relationship graph (React Flow). For
address/IP tree analysis, diff, and the IP Analyzer applet see ``analysis/`` and
``analysis.ip``.

Public API: ``registry``, ``node_from_object``, ``AnalyzerNode``, ``AnalyzerEdge``.
Edge builders for NSM-specific relations live in ``edge_sources``.
"""

from .registry import (
    AnalyzerNode,
    AnalyzerEdge,
    AnalyzerRegistry,
    node_from_object,
    registry,
)  # noqa: F401
from . import relations as _relations  # noqa: F401 – side-effects: registers resolvers

__all__ = [
    "AnalyzerNode",
    "AnalyzerEdge",
    "AnalyzerRegistry",
    "node_from_object",
    "registry",
]
