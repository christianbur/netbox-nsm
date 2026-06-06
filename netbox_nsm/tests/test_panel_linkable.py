"""Tests for TypeConfig.panel_linkable_types (Security Panel assign picker)."""

from django.contrib.contenttypes.models import ContentType

from dcim.models import Device, Interface
from ipam.models import Prefix

from rest_framework.test import APIRequestFactory

from netbox_nsm.api.serializers_.type_config import TypeConfigSerializer
from netbox_nsm.forms.object_link import ObjectLinkAssignForm, _build_type_choices
from netbox_nsm.models import PANEL_LINKABLE_DISABLED, TypeConfig
from utilities.testing import TestCase


class PanelLinkableTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.interface_ct = ContentType.objects.get_for_model(Interface)
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)
        cls.device_ct = ContentType.objects.get_for_model(Device)

        cls.zone_tc = TypeConfig.objects.create(
            name="Test Zones",
            content_type=cls.prefix_ct,
            matching_class="zone",
            panel_linkable_types=[],
        )
        cls.label_tc = TypeConfig.objects.create(
            name="Test Labels",
            content_type=cls.device_ct,
            matching_class="label",
            panel_linkable_types=[],
        )

    def test_serializer_exposes_panel_linkable_types(self):
        request = APIRequestFactory().get("/")
        data = TypeConfigSerializer(
            self.zone_tc,
            context={"request": request},
        ).data
        self.assertIn("panel_linkable_types", data)
        self.assertEqual(data["panel_linkable_types"], [])

    def test_serializer_inheritance_fields_are_read_only(self):
        serializer = TypeConfigSerializer(
            self.zone_tc,
            data={"inherit_links": False, "inherit_stop_on_own": True},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        saved = serializer.save()
        saved.refresh_from_db()
        self.assertFalse(saved.inherit_links)
        self.assertFalse(saved.inherit_stop_on_own)

    def test_queryset_panel_linkable_includes_enabled_types(self):
        qs = TypeConfig.queryset_panel_linkable()
        self.assertIn(self.zone_tc, qs)
        self.assertIn(self.label_tc, qs)

    def test_queryset_panel_linkable_excludes_disabled_types(self):
        self.zone_tc.panel_linkable_types = [PANEL_LINKABLE_DISABLED]
        self.zone_tc.save(update_fields=["panel_linkable_types"])
        qs = TypeConfig.queryset_panel_linkable()
        self.assertNotIn(self.zone_tc, qs)
        self.assertIn(self.label_tc, qs)

    def test_build_type_choices_lists_unrestricted_types(self):
        choices = dict(_build_type_choices())
        self.assertIn(self.zone_tc.content_type.pk, choices)
        self.assertIn(self.label_tc.content_type.pk, choices)

    def test_build_type_choices_skips_disabled_types(self):
        self.zone_tc.panel_linkable_types = [PANEL_LINKABLE_DISABLED]
        self.zone_tc.save(update_fields=["panel_linkable_types"])
        choices = dict(_build_type_choices())
        self.assertNotIn(self.zone_tc.content_type.pk, choices)
        self.assertIn(self.label_tc.content_type.pk, choices)

    def test_build_type_choices_filters_by_assigner_type(self):
        self.zone_tc.panel_linkable_types = [self.interface_ct.pk]
        self.zone_tc.save(update_fields=["panel_linkable_types"])
        iface_choices = dict(_build_type_choices(self.interface_ct.pk))
        prefix_choices = dict(_build_type_choices(self.prefix_ct.pk))
        self.assertIn(self.zone_tc.content_type.pk, iface_choices)
        self.assertNotIn(self.zone_tc.content_type.pk, prefix_choices)
        self.assertIn(self.label_tc.content_type.pk, prefix_choices)

    def test_form_clean_rejects_disabled_type(self):
        self.zone_tc.panel_linkable_types = [PANEL_LINKABLE_DISABLED]
        self.zone_tc.save(update_fields=["panel_linkable_types"])
        form = ObjectLinkAssignForm(
            data={
                "object_a_type_id": self.interface_ct.pk,
                "object_a_id": 1,
                "object_b_type": self.zone_tc.content_type.pk,
                "propagation": "direct",
            },
        )
        self.assertFalse(form.is_valid())
        self.assertIn("object_b_type", form.errors)

    def test_form_clean_rejects_restricted_assigner_type(self):
        self.zone_tc.panel_linkable_types = [self.interface_ct.pk]
        self.zone_tc.save(update_fields=["panel_linkable_types"])
        form = ObjectLinkAssignForm(
            data={
                "object_a_type_id": self.prefix_ct.pk,
                "object_a_id": 1,
                "object_b_type": self.zone_tc.content_type.pk,
                "propagation": "direct",
            },
        )
        self.assertFalse(form.is_valid())
        self.assertIn("object_b_type", form.errors)

    def test_form_clean_allows_restricted_assigner_type(self):
        self.zone_tc.panel_linkable_types = [self.interface_ct.pk]
        self.zone_tc.save(update_fields=["panel_linkable_types"])
        form = ObjectLinkAssignForm(
            data={
                "object_a_type_id": self.interface_ct.pk,
                "object_a_id": 1,
                "object_b_type": self.zone_tc.content_type.pk,
                "propagation": "direct",
            },
        )
        self.assertNotIn("object_b_type", form.errors)
