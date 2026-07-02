"""Tests for per-link propagation helpers."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.security.links.link_propagation import (
    should_propagate_inherited_link,
    supports_group_propagation,
    supports_ipam_propagation,
)
from netbox_nsm.security.links.link_propagation import LinkPropagationChoices


class LinkPropagationTests(SimpleTestCase):
    def test_supports_ipam_only_for_prefix(self):
        from ipam.models import Prefix

        self.assertTrue(supports_ipam_propagation(MagicMock(spec=Prefix)))
        self.assertFalse(supports_ipam_propagation(SimpleNamespace(pk=1)))

    def test_supports_group_for_cot_group_container(self):
        class FakeAddress:
            objects = MagicMock()

        obj = FakeAddress()
        obj.group = MagicMock()
        FakeAddress.objects.filter.return_value.exists.return_value = True

        self.assertTrue(supports_group_propagation(obj))

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
