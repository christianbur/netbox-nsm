"""Matrix empty-cell add URL and zone prefill on rule add forms."""

import uuid
from urllib.parse import parse_qs, urlparse

from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from core.models import ObjectType
from utilities.querydict import normalize_querydict
from extras.choices import CustomFieldTypeChoices
from utilities.testing import TestCase

from netbox_nsm.matrix.cot_matrix_tab_context import build_matrix_cell_add_href
from netbox_nsm.rulebooks.templates import RULEBOOK_GROUP
from netbox_nsm.rulebooks.views.cot_rule import (
    apply_matrix_zone_prefill,
    poly_m2m_subfield_name,
    resolve_zone_field_initial,
)


class BuildMatrixCellAddHrefTests(SimpleTestCase):
    def test_includes_zone_pks_and_return_url(self):
        request = RequestFactory().get("/")
        href = build_matrix_cell_add_href(
            "/plugins/custom-objects/nsm_rb_demo/add/",
            "/rulebooks/cot/nsm_rb_demo/rules/",
            source_zone_pk=11,
            destination_zone_pk=22,
            request=request,
        )
        query = parse_qs(urlparse(href).query)
        self.assertEqual(query["source_zone"], ["11"])
        self.assertEqual(query["destination_zone"], ["22"])
        self.assertEqual(
            query["return_url"],
            ["/rulebooks/cot/nsm_rb_demo/rules/"],
        )


class CotRuleAddZonePrefillTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField

        zone_slug = f"nsm_zone_mtx_{uuid.uuid4().hex[:8]}"
        cls.zone_cot = CustomObjectType.objects.create(
            name=zone_slug,
            slug=zone_slug,
            verbose_name="Matrix Zone",
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.zone_cot,
            name="name",
            label="Name",
            type=CustomFieldTypeChoices.TYPE_TEXT,
            primary=True,
            required=True,
        )
        zone_model = cls.zone_cot.get_model()
        cls.src_zone = zone_model.objects.create(name="trust")
        cls.dst_zone = zone_model.objects.create(name="dmz")
        zone_object_type = ObjectType.objects.get(
            app_label="netbox_custom_objects",
            model=zone_model._meta.model_name,
        )

        rb_slug = f"nsm_rb_mtx_{uuid.uuid4().hex[:8]}"
        cls.rulebook = CustomObjectType.objects.create(
            name=rb_slug,
            slug=rb_slug,
            verbose_name="Matrix Prefill Test",
            group_name=RULEBOOK_GROUP,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.rulebook,
            name="index",
            label="Index",
            type=CustomFieldTypeChoices.TYPE_INTEGER,
            primary=True,
            required=True,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.rulebook,
            name="name",
            label="Name",
            type=CustomFieldTypeChoices.TYPE_TEXT,
            required=True,
        )
        src_field = CustomObjectTypeField.objects.create(
            custom_object_type=cls.rulebook,
            name="source_zones",
            label="Zones",
            group_name="Source",
            type=CustomFieldTypeChoices.TYPE_MULTIOBJECT,
            is_polymorphic=True,
        )
        dst_field = CustomObjectTypeField.objects.create(
            custom_object_type=cls.rulebook,
            name="destination_zones",
            label="Zones",
            group_name="Destination",
            type=CustomFieldTypeChoices.TYPE_MULTIOBJECT,
            is_polymorphic=True,
        )
        src_field.related_object_types.set([zone_object_type])
        dst_field.related_object_types.set([zone_object_type])
        cls.rule_model = cls.rulebook.get_model()
        cls.rule_model.objects.create(index=10, name="existing")
        cls.zone_sub_name = poly_m2m_subfield_name(
            "source_zones",
            "netbox_custom_objects",
            zone_model._meta.model_name,
        )

    def _add_url(self, **params):
        return reverse(
            "plugins:netbox_custom_objects:customobject_add",
            kwargs={"custom_object_type": self.rulebook.slug},
        ), params

    def test_resolve_zone_field_initial_polymorphic(self):
        resolved = resolve_zone_field_initial(
            self.rulebook,
            "source_zones",
            self.src_zone.pk,
        )
        self.assertIsNotNone(resolved)
        sub_name, pks = resolved
        self.assertEqual(sub_name, self.zone_sub_name)
        self.assertEqual(pks, [self.src_zone.pk])

    def test_apply_matrix_zone_prefill_maps_both_fields(self):
        initial = {
            "source_zone": str(self.src_zone.pk),
            "destination_zone": str(self.dst_zone.pk),
            "index": "30",
        }
        apply_matrix_zone_prefill(self.rulebook, initial)
        self.assertNotIn("source_zone", initial)
        self.assertNotIn("destination_zone", initial)
        self.assertEqual(initial[self.zone_sub_name], [self.src_zone.pk])
        dst_sub_name = poly_m2m_subfield_name(
            "destination_zones",
            "netbox_custom_objects",
            self.src_zone._meta.model_name,
        )
        self.assertEqual(initial[dst_sub_name], [self.dst_zone.pk])

    def test_add_form_prefills_zones_from_query_params(self):
        from netbox_custom_objects.views import CustomObjectEditView

        self.add_permissions(
            f"netbox_custom_objects.view_{self.rule_model._meta.model_name}",
            f"netbox_custom_objects.add_{self.rule_model._meta.model_name}",
        )
        url, _ = self._add_url()
        request = RequestFactory().get(
            url,
            {
                "source_zone": self.src_zone.pk,
                "destination_zone": self.dst_zone.pk,
            },
        )
        request.user = self.user
        view = CustomObjectEditView()
        view.setup(request, custom_object_type=self.rulebook.slug)
        view.object = view.get_object()
        form_class = view.get_form(view.object._meta.model)
        form = form_class(
            instance=view.object,
            initial=normalize_querydict(request.GET),
        )
        dst_sub_name = poly_m2m_subfield_name(
            "destination_zones",
            "netbox_custom_objects",
            self.src_zone._meta.model_name,
        )
        self.assertEqual(form.initial.get(self.zone_sub_name), [self.src_zone.pk])
        self.assertEqual(form.initial.get(dst_sub_name), [self.dst_zone.pk])
