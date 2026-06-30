"""Rulebook **table** view (rules tab) — Phase C module home.

The concrete view currently lives in ``rulebooks/views/cot`` for URL stability;
this package is the canonical import path and exposes the registry spec.
"""

from __future__ import annotations

from netbox_nsm.rulebooks.views.cot import CotRulebookRulesView
from netbox_nsm.rulebooks.views.registry import RULEBOOK_VIEW_REGISTRY

__all__ = ("CotRulebookRulesView", "VIEW_SPEC")

VIEW_SPEC = next(spec for spec in RULEBOOK_VIEW_REGISTRY if spec.key == "table")
