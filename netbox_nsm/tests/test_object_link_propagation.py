"""Tests for ObjectLink ↔ nsm_object_link propagation mapping."""

from django.test import SimpleTestCase

from netbox_nsm.models.object_link import LinkPropagationChoices
from netbox_nsm.objects.link_propagation import (
    COT_OBJECT_LINK_PROPAGATION_CHOICES,
    CotObjectLinkPropagationChoices,
    cot_propagation_to_native,
    native_propagation_to_cot,
)


class ObjectLinkPropagationMappingTests(SimpleTestCase):
    def test_cot_choice_set_matches_adapter(self):
        self.assertEqual(
            len(COT_OBJECT_LINK_PROPAGATION_CHOICES),
            len(set(COT_OBJECT_LINK_PROPAGATION_CHOICES)),
        )

    def test_round_trip_all_cot_values(self):
        for cot_value in COT_OBJECT_LINK_PROPAGATION_CHOICES:
            with self.subTest(cot_value=cot_value):
                propagation, stop = cot_propagation_to_native(cot_value)
                self.assertEqual(
                    native_propagation_to_cot(propagation, stop),
                    cot_value,
                )

    def test_direct_always_clears_stop_flag(self):
        propagation, stop = cot_propagation_to_native(
            CotObjectLinkPropagationChoices.DIRECT
        )
        self.assertEqual(propagation, LinkPropagationChoices.DIRECT)
        self.assertFalse(stop)

    def test_inherit_ipam_stop_maps_to_native_stop(self):
        propagation, stop = cot_propagation_to_native(
            CotObjectLinkPropagationChoices.INHERIT_IPAM_STOP
        )
        self.assertEqual(propagation, LinkPropagationChoices.INHERIT_IPAM)
        self.assertTrue(stop)

    def test_inherit_group_stop_maps_to_native_stop(self):
        propagation, stop = cot_propagation_to_native(
            CotObjectLinkPropagationChoices.INHERIT_GROUP_STOP
        )
        self.assertEqual(propagation, LinkPropagationChoices.INHERIT_GROUP)
        self.assertTrue(stop)
