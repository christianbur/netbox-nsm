"""Fields card on the COT rulebook detail page."""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

from django.urls import reverse
from extras.choices import CustomFieldTypeChoices

from netbox_nsm.rulebooks.rules_layout import (
    cot_field_allowed_object_labels,
    cot_field_type_display,
)
from netbox_nsm.rulebooks.templates import RULEBOOK_GROUP
from netbox_nsm.rulebooks.views.cot import CotRulebookView
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


class CotRulebookColumnsViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from core.models import ObjectType
        from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField

        cls.rulebook = CustomObjectType.objects.create(
            name="nsm_rb_columns_test",
            slug="nsm_rb_columns_test",
            verbose_name="Columns Test",
            group_name=RULEBOOK_GROUP,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.rulebook,
            name="index",
            label="Index",
            type=CustomFieldTypeChoices.TYPE_INTEGER,
            primary=True,
            required=True,
            weight=1,
        )
        zone_cot = CustomObjectType.objects.create(
            name="nsm_zone_columns_test",
            slug=f"nsm_zone_columns_test_{uuid.uuid4().hex[:8]}",
            verbose_name="Zone",
        )
        zone_model = zone_cot.get_model()
        zone_object_type = ObjectType.objects.get(
            app_label="netbox_custom_objects",
            model=zone_model._meta.model_name,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.rulebook,
            name="source_zones",
            label="Source Zones",
            type=CustomFieldTypeChoices.TYPE_MULTIOBJECT,
            related_object_type=zone_object_type,
            weight=2,
        )

    def test_detail_page_renders_fields_card(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse(
            "plugins:netbox_nsm:cot_rulebook",
            kwargs={"slug": self.rulebook.slug},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ">Fields</h2>", html=False)
        self.assertContains(response, ">Field</th>", html=False)
        self.assertContains(response, ">Label</th>", html=False)
        self.assertContains(response, ">Type</th>", html=False)
        self.assertContains(response, "<code>index</code>", html=False)
        self.assertContains(response, "<td>Index</td>", html=False)
        self.assertContains(response, "<td>Integer</td>", html=False)
        self.assertContains(response, "<td>Multiple objects</td>", html=False)
        self.assertContains(response, "Custom Objects &gt; Zone", html=False)
        self.assertContains(response, "mdi-asterisk", html=False)
        self.assertNotContains(response, "mdi-pencil", html=False)

    def test_cot_field_groups_view_helper(self):
        view = CotRulebookView()
        field_groups = view._cot_field_groups(self.rulebook)
        fields = [field for group in field_groups.values() for field in group]
        by_name = {field.name: field for field in fields}
        self.assertEqual(cot_field_type_display(by_name["index"]), "Integer")
        self.assertEqual(
            cot_field_type_display(by_name["source_zones"]),
            "Multiple objects (Zone)",
        )
        self.assertTrue(by_name["index"].required)
        self.assertTrue(by_name["index"].primary)
