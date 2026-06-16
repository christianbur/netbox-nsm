"""Tests for NSM custom object list views."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.views.nsm_objects import (
    _non_sortable_polymorphic_object_fields,
    _strip_blocked_ordering,
)


class NonSortablePolymorphicFieldTests(SimpleTestCase):
    def test_returns_polymorphic_object_field_names(self):
        from extras.choices import CustomFieldTypeChoices

        address_field = MagicMock()
        address_field.name = "address"
        cot = MagicMock()
        cot.fields.filter.return_value.values_list.return_value = ["address"]

        names = _non_sortable_polymorphic_object_fields(cot)

        self.assertEqual(names, frozenset({"address"}))
        cot.fields.filter.assert_called_once_with(
            type=CustomFieldTypeChoices.TYPE_OBJECT,
            is_polymorphic=True,
        )

    def test_strip_blocked_ordering(self):
        blocked = frozenset({"address"})
        self.assertEqual(
            _strip_blocked_ordering(("name", "-address"), blocked),
            ("name",),
        )


class NsmAddressListSortTests(SimpleTestCase):
    @patch("netbox_custom_objects.views.CustomObjectListView.get_table")
    def test_prepares_request_before_super_get_table(self, super_get_table):
        from netbox_nsm.views.nsm_objects import NsmCustomObjectListView

        cot = MagicMock()
        table = MagicMock()
        table.base_columns = {"address": MagicMock(orderable=True)}
        table.order_by = ("-address", "name")
        super_get_table.return_value = table

        view = NsmCustomObjectListView()
        view.custom_object_type = cot

        with patch.object(
            view,
            "_prepare_list_table_request",
            side_effect=lambda request: request,
        ) as prepare_fn:
            with patch(
                "netbox_nsm.views.cot_list_table._non_sortable_polymorphic_object_fields",
                return_value=frozenset({"address"}),
            ):
                view.get_table(MagicMock(), MagicMock())

        prepare_fn.assert_called_once()
        self.assertFalse(table.base_columns["address"].orderable)
        self.assertEqual(table.order_by, ("name",))


class CustomObjectListPolymorphicSortPatchTests(SimpleTestCase):
    @patch("netbox_custom_objects.views.CustomObjectListView.get_table")
    def test_patch_strips_polymorphic_ordering(self, original_get_table):
        from netbox_custom_objects.views import CustomObjectListView

        from netbox_nsm.views.cot_list_table import apply_cot_polymorphic_list_table_patch

        CustomObjectListView.get_table = original_get_table
        if hasattr(CustomObjectListView.get_table, "_nsm_polymorphic_sort_patch"):
            delattr(CustomObjectListView.get_table, "_nsm_polymorphic_sort_patch")

        cot = MagicMock()
        table = MagicMock()
        table.base_columns = {"address": MagicMock(orderable=True)}
        table.order_by = ("address",)
        original_get_table.return_value = table

        view = CustomObjectListView()
        view.custom_object_type = cot

        with patch(
            "netbox_nsm.views.cot_list_table._non_sortable_polymorphic_object_fields",
            return_value=frozenset({"address"}),
        ):
            apply_cot_polymorphic_list_table_patch()
            view.get_table(MagicMock(), MagicMock())

        self.assertFalse(table.base_columns["address"].orderable)
        self.assertEqual(table.order_by, ())
