"""
Register NSM junction tables with netbox_branching.

``Rule`` / ``ObjectGroup`` use ``PrimaryModel`` (branch-aware). Child rows
(``RuleObjectItem``, …) are plain ``models.Model`` and would otherwise write to
``main`` while their parent lives in the branch schema → FK violations on save.
Same pattern as ``extras.taggeditem`` in ``INCLUDE_MODELS``.
"""

from __future__ import annotations

__all__ = (
    "NSM_BRANCHING_INCLUDE_MODELS",
    "register_branching_models",
)

# app_label.model_name — must match Django meta labels exactly
NSM_BRANCHING_INCLUDE_MODELS = (
    "netbox_nsm.ruleobjectitem",
    "netbox_nsm.rulegroupitem",
    "netbox_nsm.objectgroupmember",
    "netbox_nsm.rulebookfield",
    "netbox_nsm.rulebookfieldtype",
)


def register_branching_models() -> None:
    """Extend netbox_branching ``INCLUDE_MODELS`` and ``supports_branching()``."""
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
