"""Tests for netbox_branching junction-table registration."""

from django.test import SimpleTestCase

from netbox_nsm.branching_support import NSM_BRANCHING_INCLUDE_MODELS, register_branching_models


class BranchingSupportTests(SimpleTestCase):
    def test_register_extends_include_models(self):
        import netbox_branching.constants as bc
        import netbox_branching.utilities as bu

        original_constants = bc.INCLUDE_MODELS
        original_utilities = getattr(bu, "INCLUDE_MODELS", original_constants)
        original_fn = bu.supports_branching

        try:
            bc.INCLUDE_MODELS = ("extras.taggeditem",)
            bu.INCLUDE_MODELS = bc.INCLUDE_MODELS
            bu.supports_branching = original_fn
            register_branching_models()
            for label in NSM_BRANCHING_INCLUDE_MODELS:
                self.assertIn(label, bc.INCLUDE_MODELS)
                self.assertIn(label, bu.INCLUDE_MODELS)
        finally:
            bc.INCLUDE_MODELS = original_constants
            bu.INCLUDE_MODELS = original_utilities
            bu.supports_branching = original_fn

    def test_supports_branching_includes_rule_object_item(self):
        import netbox_branching.constants as bc
        import netbox_branching.utilities as bu

        original_constants = bc.INCLUDE_MODELS
        original_utilities = getattr(bu, "INCLUDE_MODELS", original_constants)
        original_fn = bu.supports_branching

        try:
            register_branching_models()
            from netbox_nsm.models import RuleObjectItem

            self.assertTrue(bu.supports_branching(RuleObjectItem))
        finally:
            bc.INCLUDE_MODELS = original_constants
            bu.INCLUDE_MODELS = original_utilities
            bu.supports_branching = original_fn
