"""Tests for rulebook COT form hooks (short poly sub-field labels)."""

import uuid

from django.urls import reverse

from core.models import ObjectType
from utilities.testing import TestCase

from netbox_nsm.rulebooks.templates import RULEBOOK_GROUP
from netbox_nsm.templatetags.cot_form import is_nsm_rulebook_cot_slug, poly_m2m_tab_label


class CotPolyM2mTabLabelTests(TestCase):
    def test_poly_m2m_tab_label_extracts_type_suffix(self):
        self.assertEqual(poly_m2m_tab_label("Zones (Source) (Zone)"), "Zone")
        self.assertEqual(poly_m2m_tab_label("Addresses (Source) (Address)"), "Address")

    def test_is_nsm_rulebook_cot_slug(self):
        self.assertTrue(is_nsm_rulebook_cot_slug("nsm_rb_test01"))
        self.assertFalse(is_nsm_rulebook_cot_slug("nsm_rb_0001_template"))
        self.assertFalse(is_nsm_rulebook_cot_slug("nsm_zone"))


class CotPolyM2mEditFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField

        slug = f"nsm_rb_poly_tabs_{uuid.uuid4().hex[:8]}"
        cls.cot = CustomObjectType.objects.create(
            name=slug,
            slug=slug,
            verbose_name="Poly Tabs Test",
            group_name=RULEBOOK_GROUP,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.cot,
            name="index",
            label="Index",
            type="integer",
            primary=True,
            required=True,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.cot,
            name="name",
            label="Name",
            type="text",
            weight=3,
        )
        cls.poly_field = CustomObjectTypeField.objects.create(
            custom_object_type=cls.cot,
            name="source_addresses",
            label="Addresses",
            group_name="Source",
            type="multiobject",
            is_polymorphic=True,
            weight=13,
        )
        type_a_slug = f"poly_type_a_{uuid.uuid4().hex[:8]}"
        type_b_slug = f"poly_type_b_{uuid.uuid4().hex[:8]}"
        cls.type_a = CustomObjectType.objects.create(
            name=type_a_slug,
            slug=type_a_slug,
            verbose_name="Type A",
        )
        cls.type_b = CustomObjectType.objects.create(
            name=type_b_slug,
            slug=type_b_slug,
            verbose_name="Type B",
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.type_a,
            name="name",
            label="Name",
            type="text",
            primary=True,
            required=True,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.type_b,
            name="name",
            label="Name",
            type="text",
            primary=True,
            required=True,
        )
        model_a = cls.type_a.get_model()
        model_b = cls.type_b.get_model()
        cls.poly_field.related_object_types.set(
            [
                ObjectType.objects.get(
                    app_label="netbox_custom_objects",
                    model=model_a._meta.model_name,
                ),
                ObjectType.objects.get(
                    app_label="netbox_custom_objects",
                    model=model_b._meta.model_name,
                ),
            ]
        )
        cls.model = cls.cot.get_model()
        cls.rule = cls.model.objects.create(index=1, name="rule-1")

    def _edit_url(self, pk=None):
        return reverse(
            "plugins:netbox_custom_objects:customobject_edit",
            kwargs={"custom_object_type": self.cot.slug, "pk": pk or self.rule.pk},
        )

    def _add_url(self):
        return reverse(
            "plugins:netbox_custom_objects:customobject_add",
            kwargs={"custom_object_type": self.cot.slug},
        )

    def test_rulebook_edit_form_shortens_poly_subfield_labels(self):
        self.add_permissions(
            f"netbox_custom_objects.view_{self.model._meta.model_name}",
            f"netbox_custom_objects.change_{self.model._meta.model_name}",
        )
        response = self.client.get(self._edit_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Type A"')
        self.assertContains(response, 'aria-label="Type B"')
        self.assertNotContains(response, "Addresses (Source) (Address)")

    def test_rulebook_add_form_prefills_index(self):
        self.add_permissions(
            f"netbox_custom_objects.view_{self.model._meta.model_name}",
            f"netbox_custom_objects.add_{self.model._meta.model_name}",
        )
        response = self.client.get(self._add_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="2"')

    def test_non_rulebook_cot_keeps_stacked_poly_fields(self):
        from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField

        slug = f"other-poly-{uuid.uuid4().hex[:8]}"
        cot = CustomObjectType.objects.create(
            name="Other Poly",
            slug=slug,
            verbose_name_plural="Other Polys",
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cot,
            name="name",
            label="Name",
            type="text",
            primary=True,
            required=True,
        )
        poly_field = CustomObjectTypeField.objects.create(
            custom_object_type=cot,
            name="members",
            label="Members",
            type="multiobject",
            is_polymorphic=True,
        )
        ref_slug = f"poly_ref_{uuid.uuid4().hex[:8]}"
        ref_cot = CustomObjectType.objects.create(
            name=ref_slug,
            slug=ref_slug,
            verbose_name="Ref",
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=ref_cot,
            name="name",
            label="Name",
            type="text",
            primary=True,
            required=True,
        )
        ref_model = ref_cot.get_model()
        poly_field.related_object_types.set(
            [
                ObjectType.objects.get(
                    app_label="netbox_custom_objects",
                    model=ref_model._meta.model_name,
                )
            ]
        )
        model = cot.get_model()
        obj = model.objects.create(name="x")
        self.add_permissions(
            f"netbox_custom_objects.view_{model._meta.model_name}",
            f"netbox_custom_objects.change_{model._meta.model_name}",
        )
        url = reverse(
            "plugins:netbox_custom_objects:customobject_edit",
            kwargs={"custom_object_type": cot.slug, "pk": obj.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<h3")
