"""Tests for link-table COT service layer."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.models.object_link import LinkPropagationChoices
from netbox_nsm.security.links.link_propagation import (
    CotObjectLinkPropagationChoices,
    cot_propagation_choices_for_form,
    cot_propagation_display,
    native_propagation_to_cot,
)
from netbox_nsm.security.links.cot_link_schema import (
    ObjectLinkSchema,
    classify_object_link_field_names,
    get_object_link_cot,
)
from netbox_nsm.security.links.object_link_service import (
    ObjectLinkRecord,
    classify_link_endpoints,
    get_object_link_model,
    iter_links_for_object,
)


def _test_schema(*, host_field="netbox_object", policy_field="policy_object"):
    return ObjectLinkSchema(
        cot=SimpleNamespace(pk=99, get_model=lambda: MagicMock()),
        host_field=host_field,
        policy_field=policy_field,
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
    @patch("netbox_nsm.security.links.object_link_service.is_linkable_content_type")
    @patch("netbox_nsm.security.links.object_link_service.ContentType")
    def test_netbox_host_and_policy_object_order(self, is_linkable, ct_cls):
        prefix = SimpleNamespace(pk=1)
        zone = SimpleNamespace(pk=2)

        def _linkable(content_type_id):
            return content_type_id == 20

        is_linkable.side_effect = _linkable

        prefix_ct = SimpleNamespace(pk=10, model="prefix")
        zone_ct = SimpleNamespace(pk=20, model="nsmzone")
        ct_cls.objects.get_for_model.side_effect = [prefix_ct, zone_ct]

        netbox, policy = classify_link_endpoints(prefix, zone)
        self.assertIs(netbox, prefix)
        self.assertIs(policy, zone)


class ObjectLinkSchemaTests(SimpleTestCase):
    @patch("netbox_nsm.security.links.cot_link_schema.is_linkable_content_type")
    def test_classify_fields_by_related_type_linkability(self, mock_linkable):
        host_field = SimpleNamespace(
            name="inventory_side",
            related_object_type=SimpleNamespace(pk=1),
            related_object_types=MagicMock(all=lambda: []),
        )
        policy_field = SimpleNamespace(
            name="policy_side",
            related_object_type=None,
            related_object_types=MagicMock(
                all=lambda: [SimpleNamespace(pk=2), SimpleNamespace(pk=3)]
            ),
        )

        def _linkable(ct_id):
            return ct_id in {2, 3}

        mock_linkable.side_effect = _linkable

        host_name, policy_name = classify_object_link_field_names(
            [host_field, policy_field]
        )

        self.assertEqual(host_name, "inventory_side")
        self.assertEqual(policy_name, "policy_side")

    @patch("netbox_nsm.security.links.cot_link_schema.cot_link_table_flag")
    @patch("netbox_nsm.security.links.cot_link_schema.CustomObjectType")
    def test_get_object_link_cot_uses_link_table_flag_not_slug(
        self, cot_model, mock_flag
    ):
        flagged = SimpleNamespace(slug="renamed_object_link")
        other = SimpleNamespace(slug="nsm_zone")
        cot_model.objects.all.return_value = [other, flagged]
        mock_flag.side_effect = lambda cot: cot is flagged

        self.assertIs(get_object_link_cot(), flagged)

    @patch("netbox_nsm.security.links.object_link_service.get_object_link_schema")
    def test_get_object_link_model_from_schema(self, mock_schema):
        model = MagicMock()
        mock_schema.return_value = SimpleNamespace(
            cot=SimpleNamespace(get_model=lambda: model)
        )

        self.assertIs(get_object_link_model(), model)


class ObjectLinkRecordTests(SimpleTestCase):
    def test_from_instance_maps_propagation(self):
        schema = _test_schema()
        host = SimpleNamespace(pk=1)
        policy = SimpleNamespace(pk=2)
        inst = SimpleNamespace(
            pk=5,
            propagation=CotObjectLinkPropagationChoices.INHERIT_GROUP_STOP,
            comment="note",
            netbox_object=host,
            policy_object=policy,
        )
        record = ObjectLinkRecord.from_instance(inst, schema)
        self.assertEqual(record.propagation, LinkPropagationChoices.INHERIT_GROUP)
        self.assertTrue(record.propagate_stop_on_own)
        self.assertEqual(record.comment, "note")
        self.assertIs(record.netbox_object, host)
        self.assertIs(record.policy_object, policy)

    def test_cot_propagation_round_trip(self):
        schema = _test_schema()
        inst = SimpleNamespace(
            pk=1,
            propagation=native_propagation_to_cot(
                LinkPropagationChoices.INHERIT_IPAM, True
            ),
            comment="",
            netbox_object=None,
            policy_object=None,
        )
        record = ObjectLinkRecord.from_instance(inst, schema)
        self.assertEqual(
            record.cot_propagation,
            CotObjectLinkPropagationChoices.INHERIT_IPAM_STOP,
        )


class IterLinksForObjectTests(SimpleTestCase):
    @patch("netbox_nsm.security.links.object_link_service._filter_instances_by_object_ref")
    @patch("netbox_nsm.security.links.object_link_service.get_object_link_model")
    @patch("netbox_nsm.security.links.object_link_service.get_object_link_schema")
    def test_yields_fwd_and_rev(self, mock_schema, get_model, filter_fn):
        schema = _test_schema()
        mock_schema.return_value = schema
        get_model.return_value = MagicMock()
        page = SimpleNamespace(pk=99)
        fwd_row = SimpleNamespace(
            pk=1,
            propagation=CotObjectLinkPropagationChoices.DIRECT,
            comment="",
            netbox_object=page,
            policy_object=SimpleNamespace(pk=2),
            link_type="policy",
        )
        rev_row = SimpleNamespace(
            pk=2,
            propagation=CotObjectLinkPropagationChoices.DIRECT,
            comment="",
            netbox_object=SimpleNamespace(pk=3),
            policy_object=page,
            link_type="policy",
        )
        filter_fn.side_effect = [[fwd_row], [rev_row]]

        pairs = list(iter_links_for_object(page))
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0][1], "fwd")
        self.assertEqual(pairs[1][1], "rev")
        filter_fn.assert_any_call(get_model.return_value, schema.host_field, page)
        filter_fn.assert_any_call(get_model.return_value, schema.policy_field, page)
