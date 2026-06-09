"""
Register NSM junction tables with netbox_branching.

No NSM junction tables are registered after legacy ObjectGroupMember removal
(migration 0005). This module remains as a no-op hook for future branch-aware
junction models.
"""

from __future__ import annotations

__all__ = (
    "NSM_BRANCHING_INCLUDE_MODELS",
    "register_branching_models",
)

NSM_BRANCHING_INCLUDE_MODELS: tuple[str, ...] = ()


def register_branching_models() -> None:
    """Extend netbox_branching ``INCLUDE_MODELS`` and ``supports_branching()``."""
    if not NSM_BRANCHING_INCLUDE_MODELS:
        return

    try:
        import netbox_branching.constants as branching_constants
        import netbox_branching.utilities as branching_utilities
    except ImportError:
        return

    existing = set(branching_constants.INCLUDE_MODELS)
    added = tuple(m for m in NSM_BRANCHING_INCLUDE_MODELS if m not in existing)
    if added:
        extended = branching_constants.INCLUDE_MODELS + added
        branching_constants.INCLUDE_MODELS = extended
        branching_utilities.INCLUDE_MODELS = extended

    if getattr(branching_utilities, "_nsm_branching_patched", False):
        return

    _extra = frozenset(NSM_BRANCHING_INCLUDE_MODELS)
    _original = branching_utilities.supports_branching

    def supports_branching(model):
        label = f"{model._meta.app_label}.{model._meta.model_name}"
        if label in _extra:
            return True
        return _original(model)

    branching_utilities.supports_branching = supports_branching
    branching_utilities._nsm_branching_patched = True
