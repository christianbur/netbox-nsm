"""NSM address / IP analysis package.

Submodules by concern:
  - ``addr_*`` — tree building, IP refs, navigation, merge, diff
  - ``ipa_*`` — IP Analyzer applet object tree and add-object categories
  - ``ipam_drilldown`` — prefix/range drilldown and stats
  - ``addr_analysis_utils`` — stable re-export / unittest patch surface
  - ``_lazy_api`` — breaks circular imports between implementation modules

For the Object Analyzer graph see ``netbox_nsm.analyzer`` (not this package).

IP Analyzer architecture: ``docs/ip_analyzer_architecture.md``.
"""

from __future__ import annotations

from typing import Any

__all__ = (
    "build_multi_object_addr_analysis",
    "object_is_addr_analyzable",
    "object_supports_addr_analysis",
    "parse_ipa_column_selections",
)


def __getattr__(name: str) -> Any:
    """Lazy public API — avoid eager imports that break the _lazy_api cycle."""
    if name in __all__:
        import netbox_nsm.analysis.addr_analysis_utils as utils

        return getattr(utils, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
