"""Unit tests for group M2M relation helpers."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from netbox_nsm.group_m2m import (
    GROUP_M2M_LABEL_MEMBER,
    GROUP_M2M_LABEL_MEMBER_OF,
    group_m2m_panel_type_key,
    group_m2m_panel_type_label,
    iter_group_m2m_relations,
)


def _addr_model():
    """Fresh model class with isolated ``objects`` mock per test."""
    return type("_AddrModel", (), {"objects": MagicMock()})


class GroupM2mRelationTests(SimpleTestCase):
    def test_panel_type_key_splits_member_sides(self):
        self.assertEqual(
            group_m2m_panel_type_key("app__model", GROUP_M2M_LABEL_MEMBER_OF),
            "app__model__member_of",
        )
        self.assertEqual(
            group_m2m_panel_type_key("app__model", GROUP_M2M_LABEL_MEMBER),
            "app__model__member",
        )

    def test_panel_type_label_splits_member_sides(self):
        self.assertEqual(
            group_m2m_panel_type_label("Addresses", GROUP_M2M_LABEL_MEMBER_OF),
            "Addresses — Member of",
        )
        self.assertEqual(
            group_m2m_panel_type_label("Addresses", GROUP_M2M_LABEL_MEMBER),
            "Addresses — Member",
        )

    def test_yields_parent_groups_then_members(self):
        model = _addr_model()
        parent = SimpleNamespace(pk=6, name="g-all")
        member = SimpleNamespace(pk=21, name="dev-1")

        group_rel = MagicMock()
        group_rel.all.return_value.order_by.return_value = [member]

        obj = model()
        obj.pk = 20
        obj.name = "group-1"
        obj.group = group_rel
        model.objects.filter.return_value.order_by.return_value = [parent]

        results = list(iter_group_m2m_relations(obj))

        model.objects.filter.assert_called_once_with(group=obj)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].related, parent)
        self.assertEqual(results[0].label, GROUP_M2M_LABEL_MEMBER_OF)
        self.assertEqual(results[1].related, member)
        self.assertEqual(results[1].label, GROUP_M2M_LABEL_MEMBER)

    def test_member_also_sees_peer_members(self):
        model = _addr_model()
        parent = SimpleNamespace(pk=6, name="g-all")
        peer = SimpleNamespace(pk=21, name="dev-1")

        parent.group = MagicMock()
        parent.group.all.return_value.order_by.return_value = [
            obj_placeholder := SimpleNamespace(pk=20, name="me"),
            peer,
        ]

        obj = obj_placeholder
        obj.group = MagicMock()
        model.objects.filter.return_value.order_by.return_value = [parent]

        results = list(iter_group_m2m_relations(obj))

        self.assertEqual(results[0].label, GROUP_M2M_LABEL_MEMBER_OF)
        self.assertEqual(results[1].related, peer)
        self.assertEqual(results[1].label, GROUP_M2M_LABEL_MEMBER)
        self.assertEqual(results[1].via, "g-all")

    def test_skips_self_in_member_list(self):
        model = _addr_model()
        obj = model()
        obj.pk = 20
        obj.name = "group-1"
        group_rel = MagicMock()
        group_rel.all.return_value.order_by.return_value = [obj]
        obj.group = group_rel

        model.objects.filter.return_value.order_by.return_value = []

        self.assertEqual(list(iter_group_m2m_relations(obj)), [])

    def test_no_group_field_yields_nothing(self):
        obj = SimpleNamespace(pk=1, name="plain")
        self.assertEqual(list(iter_group_m2m_relations(obj)), [])
