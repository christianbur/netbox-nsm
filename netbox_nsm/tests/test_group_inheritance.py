"""Tests for group / member-of NSM link inheritance."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.objects.group_inheritance import (
    ancestor_containers_for_group_inheritance,
    direct_parent_containers,
    iter_inherited_group_nsm_links,
)
from netbox_nsm.addresses.ipam_inheritance import should_include_inherited_type
from netbox_nsm.security.links.link_propagation import LinkPropagationChoices
from netbox_nsm.security.links.object_link_service import ObjectLinkRecord
from netbox_nsm.type_metadata.specs import TYPECONFIG_SPEC_BY_SLUG


class GroupInheritanceTests(SimpleTestCase):
    def test_specs_no_longer_define_inherit_mode(self):
        self.assertNotIn("inherit_mode", TYPECONFIG_SPEC_BY_SLUG["nsm_zone"])

    def test_should_include_respects_link_propagation(self):
        link = MagicMock(
            propagation=LinkPropagationChoices.INHERIT_GROUP,
            propagate_stop_on_own=False,
        )
        self.assertTrue(
            should_include_inherited_type(
                link,
                "netbox_custom_objects__nsmlabel",
                set(),
                expected_propagation=LinkPropagationChoices.INHERIT_GROUP,
            )
        )
        self.assertFalse(
            should_include_inherited_type(
                link,
                "netbox_custom_objects__nsmlabel",
                set(),
                expected_propagation=LinkPropagationChoices.INHERIT_IPAM,
            )
        )

    def test_direct_parent_includes_cot_group_m2m(self):
        parent = SimpleNamespace(pk=3, name="parent-group")

        class FakeAddress:
            objects = MagicMock()

        obj = FakeAddress()
        obj.pk = 7
        obj.group = MagicMock()
        FakeAddress.objects.filter.return_value.order_by.return_value = [parent]

        parents = direct_parent_containers(obj)

        self.assertEqual(parents, [parent])

    @patch("netbox_nsm.objects.group_inheritance.direct_parent_containers")
    def test_ancestor_containers_walks_transitive_parents(self, direct_fn):
        g1 = SimpleNamespace(pk=1, __class__=type("NsmAddress", (), {}))
        g2 = SimpleNamespace(pk=2, __class__=g1.__class__)
        obj = SimpleNamespace(pk=99)

        direct_fn.side_effect = [
            [g1],
            [g2],
            [],
            [],
        ]

        result = ancestor_containers_for_group_inheritance(obj)
        self.assertEqual(result, [g1, g2])

    @patch("netbox_nsm.objects.group_inheritance._type_config_map")
    @patch("netbox_nsm.objects.group_inheritance.direct_nsm_type_keys_for_ipam")
    @patch("netbox_nsm.objects.group_inheritance.ancestor_containers_for_group_inheritance")
    @patch("netbox_nsm.security.links.object_link_service.iter_links_on_container")
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_iter_inherited_yields_group_links(
        self,
        content_type_cls,
        iter_links_fn,
        ancestor_fn,
        direct_keys_fn,
        tc_map_fn,
    ):
        parent = SimpleNamespace(pk=10)
        zone = SimpleNamespace(pk=99, get_absolute_url=lambda: "/zone/99/")
        zone_ct = MagicMock(pk=99, app_label="netbox_custom_objects", model="nsmzone")
        obj = SimpleNamespace(pk=5)
        obj_ct = MagicMock(pk=5)

        content_type_cls.objects.get_for_model.side_effect = [obj_ct, zone_ct]
        ancestor_fn.return_value = [parent]
        direct_keys_fn.return_value = set()

        zone_tc = MagicMock()
        tc_map_fn.return_value = {99: zone_tc}

        link = ObjectLinkRecord(
            pk=1,
            instance=SimpleNamespace(pk=1),
            comment="",
            propagation=LinkPropagationChoices.INHERIT_GROUP,
            propagate_stop_on_own=False,
            policy_object=zone,
        )
        iter_links_fn.return_value = [link]

        with patch("django.db.models.prefetch_related_objects"):
            inherited = list(iter_inherited_group_nsm_links(obj))

        self.assertEqual(len(inherited), 1)
        self.assertIs(inherited[0].linked, zone)
