"""Setup: schema bundle list, detail, preview, and apply.

.. deprecated::
    These views have been consolidated in ``netbox_nsm.bundles.views``.
    This module re-exports them for backward compatibility.
"""

from netbox_nsm.bundles.views import (  # noqa: F401
    SetupSchemaApplyView,
    SetupSchemaDetailView,
    SetupSchemaPreviewView,
)

__all__ = (
    "SetupSchemaApplyView",
    "SetupSchemaDetailView",
    "SetupSchemaPreviewView",
)
