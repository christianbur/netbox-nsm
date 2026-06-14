"""Tests for nsm_object_link COT service layer."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.models.object_link import LinkPropagationChoices
from netbox_nsm.objects.link_propagation import (
    CotObjectLinkPropagationChoices,
    cot_propagation_choices_for_form,
    cot_propagation_display,
    native_propagation_to_cot,
)
from netbox_nsm.objects.object_link_service import (
    ObjectLinkRecord,
    classify_link_endpoints,
    iter_links_for_object,
)


class CotPropagationFormChoicesTests(SimpleTestCase):
    def test_form_choices_include_stop_variants(self):
        values = [v for v, _ in cot_propagation_choices_for_form()]
        self.assertIn(CotObjectLinkPropagationChoices.INHERIT_IPAM_STOP, values)
        self.assertIn(CotObjectLinkPropagationChoices.INHERIT_GROUP_STOP, values)

    def test_display_labels_stop_modes(self):
        label = cot_propagation_display(
            CotObjectLinkPropagationChoices.INHERIT_IPAM_STOP
        )
        self.assertIn("stop", label.lower())


class ClassifyLinkEndpointsTests(SimpleTestCase):
    @patch("netbox_nsm.objects.object_link_service.is_panel_linkable_content_type")
    @patch("netbox_nsm.objects.object_link_service.ContentType")
    def test_netbox_host_and_policy_object_order(self, ct_cls, is_panel_linkable):
        prefix = SimpleNamespace(pk=1)
        zone = SimpleNamespace(pk=2)

        def _panel_linkable(content_type_id):
            return content_type_id == 20

        is_panel_linkable.side_effect = _panel_linkable

        prefix_ct = SimpleNamespace(pk=10, model="prefix")
        zone_ct = SimpleNamespace(pk=20, model="nsmzone")
        ct_cls.objects.get_for_model.side_effect = [prefix_ct, zone_ct]

        netbox, policy = classify_link_endpoints(prefix, zone)
        self.assertIs(netbox, prefix)
        self.assertIs(policy, zone)


class ObjectLinkRecordTests(SimpleTestCase):
    def test_from_instance_maps_propagation(self):
        inst = SimpleNamespace(
            pk=5,
            propagation=CotObjectLinkPropagationChoices.INHERIT_GROUP_STOP,
            comment="note",
            netbox_object=SimpleNamespace(pk=1),
            policy_object=SimpleNamespace(pk=2),
        )
        record = ObjectLinkRecord.from_instance(inst)
        self.assertEqual(record.propagation, LinkPropagationChoices.INHERIT_GROUP)
        self.assertTrue(record.propagate_stop_on_own)
        self.assertEqual(record.comment, "note")

    def test_cot_propagation_round_trip(self):
        inst = SimpleNamespace(
            pk=1,
            propagation=native_propagation_to_cot(
                LinkPropagationChoices.INHERIT_IPAM, True
            ),
            comment="",
            netbox_object=None,
            policy_object=None,
        )
        record = ObjectLinkRecord.from_instance(inst)
        self.assertEqual(
            record.cot_propagation,
            CotObjectLinkPropagationChoices.INHERIT_IPAM_STOP,
        )


class IterLinksForObjectTests(SimpleTestCase):
    @patch("netbox_nsm.objects.object_link_service._filter_instances_by_object_ref")
    @patch("netbox_nsm.objects.object_link_service.get_object_link_model")
    def test_yields_fwd_and_rev(self, get_model, filter_fn):
        get_model.return_value = MagicMock()
        page = SimpleNamespace(pk=99)
        fwd_row = SimpleNamespace(
            pk=1,
            propagation=CotObjectLinkPropagationChoices.DIRECT,
            comment="",
            netbox_object=page,
            policy_object=SimpleNamespace(pk=2),
        )
        rev_row = SimpleNamespace(
            pk=2,
            propagation=CotObjectLinkPropagationChoices.DIRECT,
            comment="",
            netbox_object=SimpleNamespace(pk=3),
            policy_object=page,
        )
        filter_fn.side_effect = [[fwd_row], [rev_row]]

        pairs = list(iter_links_for_object(page))
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0][1], "fwd")
        self.assertEqual(pairs[1][1], "rev")
