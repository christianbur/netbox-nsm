"""NSM setup wizard view.

.. deprecated::
    ``SetupView`` has been consolidated in ``netbox_nsm.bundles.views``.
    This module re-exports it and exposes ``custom_objects`` / ``setup_menu_enabled``
    at module level so that existing test patches continue to work.
"""

from netbox_nsm.bundles.views import SetupView  # noqa: F401
from netbox_nsm.core.setup_flags import setup_menu_enabled  # noqa: F401  (test patches)
from netbox_nsm.import_ import custom_objects  # noqa: F401  (test patches)

__all__ = ("SetupView",)
