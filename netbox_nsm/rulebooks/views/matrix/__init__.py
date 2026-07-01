"""Rulebook **matrix** view — Phase C module home.

Matrix engine lives in ``rulebooks/matrix/``; the concrete view currently lives in
``rulebooks/views/cot`` for URL stability. This package is the canonical import path
and exposes the registry spec.
"""

from __future__ import annotations

from netbox_nsm.rulebooks.views.cot import CotRulebookMatrixView
from netbox_nsm.rulebooks.views.registry import RULEBOOK_VIEW_REGISTRY

__all__ = ("CotRulebookMatrixView", "VIEW_SPEC")

VIEW_SPEC = next(spec for spec in RULEBOOK_VIEW_REGISTRY if spec.key == "matrix")
