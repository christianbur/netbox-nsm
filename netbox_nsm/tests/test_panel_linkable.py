"""Tests for TypeConfig.panel_linkable (Security Panel assign picker)."""

from django.contrib.contenttypes.models import ContentType

from dcim.models import Device, Interface
from ipam.models import Prefix

from netbox_nsm.api.serializers_.type_config import TypeConfigSerializer
from netbox_nsm.forms.object_link import _build_type_choices
from netbox_nsm.models import TypeConfig
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
            panel_linkable=True,
        )
        cls.label_tc = TypeConfig.objects.create(
            name="Test Labels",
            content_type=cls.device_ct,
            matching_class="label",
            panel_linkable=True,
        )

    def test_serializer_exposes_panel_linkable(self):
        data = TypeConfigSerializer(self.zone_tc).data
        self.assertIn("panel_linkable", data)
        self.assertTrue(data["panel_linkable"])

    def test_queryset_panel_linkable_includes_enabled_types(self):
        qs = TypeConfig.queryset_panel_linkable()
        self.assertIn(self.zone_tc, qs)
        self.assertIn(self.label_tc, qs)

    def test_queryset_panel_linkable_excludes_disabled_types(self):
        self.zone_tc.panel_linkable = False
        self.zone_tc.save(update_fields=["panel_linkable"])
        qs = TypeConfig.queryset_panel_linkable()
        self.assertNotIn(self.zone_tc, qs)
        self.assertIn(self.label_tc, qs)

    def test_build_type_choices_lists_panel_linkable_types(self):
        choices = dict(_build_type_choices())
        self.assertIn(self.zone_tc.content_type.pk, choices)
        self.assertIn(self.label_tc.content_type.pk, choices)

    def test_build_type_choices_skips_panel_linkable_false(self):
        self.zone_tc.panel_linkable = False
        self.zone_tc.save(update_fields=["panel_linkable"])
        choices = dict(_build_type_choices())
        self.assertNotIn(self.zone_tc.content_type.pk, choices)
        self.assertIn(self.label_tc.content_type.pk, choices)

    def test_form_clean_rejects_non_linkable_type(self):
        from netbox_nsm.forms.object_link import ObjectLinkAssignForm

        self.zone_tc.panel_linkable = False
        self.zone_tc.save(update_fields=["panel_linkable"])
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
