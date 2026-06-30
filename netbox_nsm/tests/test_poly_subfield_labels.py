"""Tests for shorter polymorphic custom-object sub-field labels."""

import uuid

from django.contrib.contenttypes.models import ContentType

from ipam.models import Prefix

from netbox_nsm.core.poly_subfield_labels import (
    poly_subfield_short_label,
    poly_subfield_type_label,
    shorten_rulebook_poly_subfield_labels,
)
from netbox_nsm.type_metadata.config import format_nsm_config_comment_yaml
from utilities.testing import TestCase


class PolySubfieldLabelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField

        slug = f"nsm-poly-label-{uuid.uuid4().hex[:8]}"
        cls.cot = CustomObjectType.objects.create(
            name="Address Group",
            verbose_name="Address Group",
            verbose_name_plural="Address Groups",
            slug=slug,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.cot,
            name="name",
            label="Name",
            type="text",
            primary=True,
            required=True,
        )
        cls.cot_ct = ContentType.objects.get_for_model(cls.cot.get_model())
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)

    def test_uses_typeconfig_content_type_label(self):
        self.cot.comments = format_nsm_config_comment_yaml(
            {
                "sort_order": 0,
                "display_template": "{{ name }}",
                "links": {"linkable": True},
            }
        ).rstrip()
        self.cot.save(update_fields=["comments"])
        self.assertEqual(poly_subfield_type_label(self.cot_ct.pk), "Address Group")

    def test_fallback_omits_app_prefix_without_typeconfig(self):
        self.assertEqual(poly_subfield_type_label(self.prefix_ct.pk), "Prefix")

    def test_poly_subfield_short_label_extracts_type_suffix(self):
        self.assertEqual(poly_subfield_short_label("Zones (Source) (Zone)"), "Zone")
        self.assertEqual(
            poly_subfield_short_label("Addresses (Source) (Address)"), "Address"
        )
        self.assertEqual(poly_subfield_short_label("Service"), "Service")

    def test_shorten_rulebook_poly_subfield_labels(self):
        from django import forms

        form = forms.Form()
        sub_a = "source_addresses__netbox_custom_objects__table1model"
        sub_b = "source_addresses__ipam__prefix"
        form.fields = {
            sub_a: forms.Field(label="Addresses (Source) (Address Group)"),
            sub_b: forms.Field(label="Addresses (Source) (Prefix)"),
        }
        form.custom_object_type_poly_m2m_groups = {
            sub_a: ([sub_a, sub_b], "Addresses (Source)"),
        }
        shorten_rulebook_poly_subfield_labels(form)
        self.assertEqual(form.fields[sub_a].label, "Address Group")
        self.assertEqual(form.fields[sub_b].label, "Prefix")
