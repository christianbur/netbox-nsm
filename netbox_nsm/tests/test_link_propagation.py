"""Tests for per-link propagation helpers."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.link_propagation import (
    object_link_panel_link_type,
    object_link_panel_user_comment,
    propagation_choices_for_object,
    should_propagate_inherited_link,
    supports_group_propagation,
    supports_ipam_propagation,
)
from netbox_nsm.models.object_link import LinkPropagationChoices


class LinkPropagationTests(SimpleTestCase):
    def test_supports_ipam_only_for_prefix(self):
        from ipam.models import Prefix

        self.assertTrue(supports_ipam_propagation(MagicMock(spec=Prefix)))
        self.assertFalse(supports_ipam_propagation(SimpleNamespace(pk=1)))

    def test_supports_group_for_object_group(self):
        from netbox_nsm.models import ObjectGroup

        self.assertTrue(supports_group_propagation(MagicMock(spec=ObjectGroup)))

    def test_propagation_choices_always_include_all_modes(self):
        obj = SimpleNamespace(pk=1)
        values = [v for v, _ in propagation_choices_for_object(obj)]
        self.assertEqual(
            values,
            [
                LinkPropagationChoices.DIRECT,
                LinkPropagationChoices.INHERIT_IPAM,
                LinkPropagationChoices.INHERIT_GROUP,
            ],
        )
        # Same result without source object (forms always show every mode).
        self.assertEqual(
            [v for v, _ in propagation_choices_for_object()],
            values,
        )

    def test_should_propagate_respects_mode_and_stop_on_own(self):
        link = MagicMock(
            propagation=LinkPropagationChoices.INHERIT_IPAM,
            propagate_stop_on_own=True,
        )
        covered = {"app__zone"}
        self.assertFalse(
            should_propagate_inherited_link(
                link,
                "app__zone",
                covered,
                expected_propagation=LinkPropagationChoices.INHERIT_IPAM,
            )
        )
        self.assertTrue(
            should_propagate_inherited_link(
                link,
                "app__label",
                covered,
                expected_propagation=LinkPropagationChoices.INHERIT_IPAM,
            )
        )

    def test_panel_splits_link_type_and_user_comment(self):
        link = MagicMock(
            get_propagation_display=MagicMock(
                return_value="Inherit to IPAM children (prefixes, addresses, ranges)"
            ),
            propagate_stop_on_own=False,
            comment="  edge case  ",
        )
        self.assertEqual(
            object_link_panel_link_type(link),
            "Inherit to IPAM children (prefixes, addresses, ranges)",
        )
        self.assertEqual(object_link_panel_user_comment(link), "edge case")

    def test_direct_propagation_never_inherits(self):
        link = MagicMock(
            propagation=LinkPropagationChoices.DIRECT,
            propagate_stop_on_own=False,
        )
        self.assertFalse(
            should_propagate_inherited_link(
                link,
                "app__zone",
                set(),
                expected_propagation=LinkPropagationChoices.INHERIT_IPAM,
            )
        )
