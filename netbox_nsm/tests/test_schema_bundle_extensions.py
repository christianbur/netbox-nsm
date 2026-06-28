"""Tests for bundle seed apply/diff with portable object references."""

import uuid

from core.models import ObjectType
from extras.choices import CustomFieldTypeChoices
from utilities.testing import TestCase

from netbox_nsm.bundles.bundle_extensions import apply_seed_objects, diff_seed_objects


class BundleSeedPortableRefTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField

        suffix = uuid.uuid4().hex[:8]
        cls.service_slug = f"nsm_service_{suffix}"
        cls.group_slug = f"nsm_service_group_{suffix}"

        cls.service_cot = CustomObjectType.objects.create(
            name=cls.service_slug,
            slug=cls.service_slug,
            verbose_name="Service",
            verbose_name_plural="Services",
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.service_cot,
            name="name",
            label="Name",
            type=CustomFieldTypeChoices.TYPE_TEXT,
            primary=True,
            required=True,
        )

        cls.group_cot = CustomObjectType.objects.create(
            name=cls.group_slug,
            slug=cls.group_slug,
            verbose_name="Service Group",
            verbose_name_plural="Service Groups",
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.group_cot,
            name="name",
            label="Name",
            type=CustomFieldTypeChoices.TYPE_TEXT,
            primary=True,
            required=True,
        )
        service_model = cls.service_cot.get_model()
        service_object_type = ObjectType.objects.get(
            app_label="netbox_custom_objects",
            model=service_model._meta.model_name,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.group_cot,
            name="group",
            label="Group Members",
            type=CustomFieldTypeChoices.TYPE_MULTIOBJECT,
            required=True,
            related_object_type=service_object_type,
        )

    def test_apply_seed_objects_resolves_portable_multiobject_refs(self):
        objects = [
            {
                "type": self.service_slug,
                "records": [
                    {"name": "DNS-UDP"},
                    {"name": "DNS-TCP"},
                ],
            },
            {
                "type": self.group_slug,
                "records": [
                    {
                        "name": "G-DNS",
                        "group": [
                            f"{self.service_slug}/DNS-UDP",
                            f"{self.service_slug}/DNS-TCP",
                        ],
                    }
                ],
            },
        ]

        count = apply_seed_objects(objects)
        self.assertEqual(count, 3)

        group_model = self.group_cot.get_model()
        group = group_model.objects.get(name="G-DNS")
        member_names = sorted(group.group.values_list("name", flat=True))
        self.assertEqual(member_names, ["DNS-TCP", "DNS-UDP"])

    def test_diff_seed_objects_reports_no_change_after_apply(self):
        objects = [
            {
                "type": self.service_slug,
                "records": [{"name": "HTTP"}],
            },
            {
                "type": self.group_slug,
                "records": [
                    {
                        "name": "G-HTTP",
                        "group": [f"{self.service_slug}/HTTP"],
                    }
                ],
            },
        ]
        apply_seed_objects(objects)
        diffs = diff_seed_objects(objects)
        self.assertEqual(diffs, [])

    def test_apply_seed_objects_missing_portable_ref_raises(self):
        objects = [
            {
                "type": self.group_slug,
                "records": [
                    {
                        "name": "G-Missing",
                        "group": [f"{self.service_slug}/does-not-exist"],
                    }
                ],
            }
        ]
        with self.assertRaises(ValueError):
            apply_seed_objects(objects)
