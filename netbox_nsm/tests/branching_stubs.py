"""Minimal netbox_branching stubs so branch tests run without the optional plugin."""

from __future__ import annotations

import contextvars
import sys
import types


def ensure_netbox_branching_stubs() -> None:
    """Register fake ``netbox_branching`` modules for ``unittest.mock.patch`` targets."""
    if getattr(sys.modules.get("netbox_branching"), "_nsm_test_stub", False):
        return

    branching = types.ModuleType("netbox_branching")
    branching._nsm_test_stub = True

    constants = types.ModuleType("netbox_branching.constants")
    constants.INCLUDE_MODELS = ("extras.taggeditem",)
    constants.COOKIE_NAME = "active_branch"
    constants.QUERY_PARAM = "_branch"

    utilities = types.ModuleType("netbox_branching.utilities")
    utilities.INCLUDE_MODELS = constants.INCLUDE_MODELS

    def supports_branching(model):
        label = f"{model._meta.app_label}.{model._meta.model_name}"
        return label in utilities.INCLUDE_MODELS

    utilities.supports_branching = supports_branching
    utilities.activate_branch = lambda branch: None

    contextvars_mod = types.ModuleType("netbox_branching.contextvars")
    contextvars_mod.active_branch = contextvars.ContextVar(
        "active_branch", default=None
    )

    models_mod = types.ModuleType("netbox_branching.models")

    class _BranchManager:
        def get(self, **kwargs):
            raise NotImplementedError

        def all(self):
            return []

    class Branch:
        objects = _BranchManager()

    models_mod.Branch = Branch

    branching.constants = constants
    branching.utilities = utilities
    branching.contextvars = contextvars_mod
    branching.models = models_mod

    sys.modules["netbox_branching"] = branching
    sys.modules["netbox_branching.constants"] = constants
    sys.modules["netbox_branching.utilities"] = utilities
    sys.modules["netbox_branching.contextvars"] = contextvars_mod
    sys.modules["netbox_branching.models"] = models_mod
