"""Display helpers for COT rulebook field columns."""

from types import SimpleNamespace
from unittest.mock import patch

from extras.choices import CustomFieldTypeChoices

from netbox_nsm.rulebooks.rules_layout import (
    cot_field_allowed_object_labels,
    cot_field_type_display,
)
from utilities.testing import TestCase


class CotFieldTypeDisplayTests(TestCase):
    def test_scalar_field_uses_type_display(self):
        field = SimpleNamespace(
            type=CustomFieldTypeChoices.TYPE_INTEGER,
            get_type_display=lambda: "Integer",
            is_polymorphic=False,
            related_object_type_id=None,
            related_object_types=SimpleNamespace(all=lambda: []),
        )
        self.assertEqual(cot_field_type_display(field), "Integer")
        self.assertEqual(cot_field_allowed_object_labels(field), [])

    def test_multiobject_single_type_includes_allowed_label(self):
        zone_cot = SimpleNamespace(
            slug="nsm_zone",
            verbose_name="Zone",
            name="nsm_zone",
        )
        object_type = SimpleNamespace(
            app_label="netbox_custom_objects",
            model="table99model",
        )
        field = SimpleNamespace(
            type=CustomFieldTypeChoices.TYPE_MULTIOBJECT,
            get_type_display=lambda: "Multiple objects",
            is_polymorphic=False,
            related_object_type_id=1,
            related_object_type=object_type,
            related_object_types=SimpleNamespace(all=lambda: []),
        )
        with patch(
            "netbox_nsm.rulebooks.rules_layout._cot_for_object_type",
            return_value=zone_cot,
        ):
            self.assertEqual(
                cot_field_allowed_object_labels(field),
                ["Zone"],
            )
            self.assertEqual(
                cot_field_type_display(field),
                "Multiple objects (Zone)",
            )

    def test_multiobject_polymorphic_lists_allowed_types(self):
        zone_cot = SimpleNamespace(
            slug="nsm_zone",
            verbose_name="Zone",
            name="nsm_zone",
        )
        label_cot = SimpleNamespace(
            slug="nsm_label",
            verbose_name="Label",
            name="nsm_label",
        )
        zone_type = SimpleNamespace(
            app_label="netbox_custom_objects",
            model="table1model",
        )
        label_type = SimpleNamespace(
            app_label="netbox_custom_objects",
            model="table2model",
        )
        field = SimpleNamespace(
            type=CustomFieldTypeChoices.TYPE_MULTIOBJECT,
            get_type_display=lambda: "Multiple objects",
            is_polymorphic=True,
            related_object_type_id=None,
            related_object_type=None,
            related_object_types=SimpleNamespace(all=lambda: [zone_type, label_type]),
        )
        def _cot_for_mock_object_type(object_type):
            if object_type.model == "table1model":
                return zone_cot
            return label_cot

        with patch(
            "netbox_nsm.rulebooks.rules_layout._cot_for_object_type",
            side_effect=_cot_for_mock_object_type,
        ):
            self.assertEqual(
                cot_field_allowed_object_labels(field),
                ["Zone", "Label"],
            )
            self.assertEqual(
                cot_field_type_display(field),
                "Multiple objects (Zone, Label)",
            )
