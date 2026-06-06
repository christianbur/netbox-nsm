"""Tests for group / member-of NSM link inheritance."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.group_inheritance import (
    ancestor_containers_for_group_inheritance,
    direct_parent_containers,
    iter_inherited_group_nsm_links,
)
from netbox_nsm.ipam_inheritance import should_include_inherited_type
from netbox_nsm.models.object_link import LinkPropagationChoices
from netbox_nsm.type_config_specs import TYPECONFIG_SPEC_BY_SLUG


class GroupInheritanceTests(SimpleTestCase):
    def test_specs_no_longer_define_inherit_mode(self):
        self.assertNotIn("inherit_mode", TYPECONFIG_SPEC_BY_SLUG["nsm_zones"])

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

    @patch("netbox_nsm.group_inheritance.ObjectGroupMember")
    @patch("netbox_nsm.group_inheritance.ContentType")
    def test_direct_parent_includes_object_group_membership(
        self, content_type_cls, member_cls
    ):
        obj = SimpleNamespace(pk=7)
        group = SimpleNamespace(pk=3, name="parent-group")

        ct = MagicMock()
        content_type_cls.objects.get_for_model.return_value = ct
        member = MagicMock(group=group)
        member_cls.objects.filter.return_value.select_related.return_value = [member]

        parents = direct_parent_containers(obj)

        self.assertEqual(parents, [group])

    @patch("netbox_nsm.group_inheritance.direct_parent_containers")
    def test_ancestor_containers_walks_transitive_parents(self, direct_fn):
        g1 = SimpleNamespace(pk=1, __class__=type("ObjectGroup", (), {}))
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

    @patch("netbox_nsm.group_inheritance._type_config_map")
    @patch("netbox_nsm.group_inheritance.direct_nsm_type_keys_for_ipam")
    @patch("netbox_nsm.group_inheritance.ancestor_containers_for_group_inheritance")
    @patch("netbox_nsm.group_inheritance.ObjectLink")
    @patch("netbox_nsm.group_inheritance.ContentType")
    def test_iter_yields_group_inherited_zone(
        self,
        content_type_cls,
        object_link_cls,
        ancestor_fn,
        direct_keys_fn,
        tc_map_fn,
    ):
        obj = SimpleNamespace(pk=10)
        parent = SimpleNamespace(pk=1, get_absolute_url=lambda: "/groups/1/")
        zone = SimpleNamespace(get_absolute_url=lambda: "/zones/1/")

        zone_ct = MagicMock(pk=99, app_label="netbox_custom_objects", model="nsmzone")
        parent_ct = MagicMock(pk=20)
        obj_ct = MagicMock(pk=5)

        content_type_cls.objects.get_for_model.side_effect = [obj_ct, parent_ct]
        ancestor_fn.return_value = [parent]
        direct_keys_fn.return_value = set()

        zone_tc = MagicMock()
        tc_map_fn.return_value = {99: zone_tc}

        link = MagicMock()
        link.object_b = zone
        link.object_b_type = zone_ct
        link.propagation = LinkPropagationChoices.INHERIT_GROUP
        link.propagate_stop_on_own = False
        fwd_qs = MagicMock()
        fwd_qs.select_related.return_value = [link]
        rev_qs = MagicMock()
        rev_qs.select_related.return_value = []

        def _filter_side_effect(**kwargs):
            if kwargs.get("object_a_type") == parent_ct:
                return fwd_qs
            if kwargs.get("object_b_type") == parent_ct:
                return rev_qs
            return MagicMock(select_related=MagicMock(return_value=[]))

        object_link_cls.objects.filter.side_effect = _filter_side_effect

        with patch("netbox_nsm.group_inheritance.prefetch_related_objects"):
            items = list(iter_inherited_group_nsm_links(obj))

        self.assertEqual(len(items), 1)
        self.assertIs(items[0].linked, zone)
        self.assertIs(items[0].ancestor, parent)
