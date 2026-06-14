"""Lazy cross-module import facade for address/IP analysis internals.

Implementation modules import helpers through this module to break circular
dependencies while keeping ``addr_analysis_utils`` as the stable patch surface
for tests (``@patch("netbox_nsm.analysis.addr_analysis_utils.*")``).
"""

from __future__ import annotations

from typing import Any


def __getattr__(name: str) -> Any:
    import netbox_nsm.analysis.addr_analysis_utils as utils

    return getattr(utils, name)
