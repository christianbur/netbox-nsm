"""NSM address / IP analysis (IP Analyzer applet, addr trees, IP analysis APIs)."""

from __future__ import annotations

from typing import Any

__all__ = (
    "build_multi_object_addr_analysis",
    "object_is_addr_analyzable",
    "object_supports_addr_analysis",
    "parse_ipa_column_selections",
)


def __getattr__(name: str) -> Any:
    if name in __all__:
        import netbox_nsm.analyzers.ip.addr_analysis_utils as utils

        return getattr(utils, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
