"""Polymorphic rules-tab columns follow TypeConfig.sort_order (left to right)."""

import uuid

from django.contrib.contenttypes.models import ContentType
from extras.choices import CustomFieldTypeChoices

from netbox_nsm.objects.nsm_config import format_nsm_config_comment_yaml
from netbox_nsm.rulebooks.rules_layout import (
    build_cot_rules_layout,
    cot_field_allowed_object_labels,
)
from netbox_nsm.rulebooks.templates import RULEBOOK_GROUP
from utilities.testing import TestCase


class RulesLayoutPolyColumnOrderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from core.models import ObjectType
        from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField

        suffix = uuid.uuid4().hex[:8]

        cls.zone_cot = CustomObjectType.objects.create(
            name=f"nsm_zone_order_{suffix}",
            slug=f"nsm_zone_order_{suffix}",
            verbose_name="Zone",
        )
        cls.label_cot = CustomObjectType.objects.create(
            name=f"nsm_label_order_{suffix}",
            slug=f"nsm_label_order_{suffix}",
            verbose_name="Label",
        )
        cls.address_cot = CustomObjectType.objects.create(
            name=f"nsm_address_order_{suffix}",
            slug=f"nsm_address_order_{suffix}",
            verbose_name="Address",
        )

        cls.zone_ot = ObjectType.objects.get(
            app_label="netbox_custom_objects",
            model=cls.zone_cot.get_model()._meta.model_name,
        )
        cls.label_ot = ObjectType.objects.get(
            app_label="netbox_custom_objects",
            model=cls.label_cot.get_model()._meta.model_name,
        )
        cls.address_ot = ObjectType.objects.get(
            app_label="netbox_custom_objects",
            model=cls.address_cot.get_model()._meta.model_name,
        )

        for cot, sort_order, name in (
            (cls.zone_cot, 10, "Zones"),
            (cls.label_cot, 11, "Labels"),
            (cls.address_cot, 12, "Addresses"),
        ):
            cot.comments = format_nsm_config_comment_yaml(
                {
                    "sort_order": sort_order,
                    "display_template": "{name}",
                    "panel": {"panel_linkable": True},
                }
            ).rstrip()
            cot.save(update_fields=["comments"])

        cls.rulebook = CustomObjectType.objects.create(
            name=f"nsm_rb_order_{suffix}",
            slug=f"nsm_rb_order_{suffix}",
            verbose_name="Order Test",
            group_name=RULEBOOK_GROUP,
        )
        cls.source_field = CustomObjectTypeField.objects.create(
            custom_object_type=cls.rulebook,
            name="source",
            label="Source",
            type=CustomFieldTypeChoices.TYPE_MULTIOBJECT,
            is_polymorphic=True,
            weight=10,
        )
        # Deliberately reverse M2M order — layout must still follow sort_order.
        cls.source_field.related_object_types.set(
            [cls.address_ot, cls.label_ot, cls.zone_ot]
        )

    def test_grouped_columns_follow_typeconfig_sort_order(self):
        layout = build_cot_rules_layout(self.rulebook)
        labels = [col["label"] for col in layout["grouped_columns"]]
        self.assertEqual(labels, ["Zone", "Label", "Address"])

    def test_allowed_object_labels_follow_typeconfig_sort_order(self):
        labels = cot_field_allowed_object_labels(self.source_field)
        self.assertEqual(labels, ["Zone", "Label", "Address"])

    def test_group_columns_children_match_grouped_columns(self):
        layout = build_cot_rules_layout(self.rulebook)
        child_labels = [
            col["label"] for group in layout["header_groups"] for col in group["columns"]
        ]
        grouped_labels = [col["label"] for col in layout["grouped_columns"]]
        self.assertEqual(child_labels, grouped_labels)
        self.assertEqual(child_labels, ["Zone", "Label", "Address"])
