"""Tests for TypeConfig.panel_linkable_content_types (Security Panel assign filter)."""

from django.contrib.contenttypes.models import ContentType

from dcim.models import Device, Interface
from ipam.models import Prefix

from netbox_nsm.forms.object_link import _build_type_choices
from netbox_nsm.models import TypeConfig
from utilities.testing import TestCase


class PanelLinkableContentTypesTests(TestCase):
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

    def test_empty_m2m_allows_all_source_types(self):
        self.assertTrue(self.zone_tc.is_panel_linkable_for(self.interface_ct.pk))
        self.assertTrue(self.zone_tc.is_panel_linkable_for(self.prefix_ct.pk))

    def test_restricted_m2m_allows_only_listed_types(self):
        self.zone_tc.panel_linkable_content_types.set([self.interface_ct])
        self.assertTrue(self.zone_tc.is_panel_linkable_for(self.interface_ct.pk))
        self.assertFalse(self.zone_tc.is_panel_linkable_for(self.prefix_ct.pk))

    def test_panel_linkable_false_overrides_m2m(self):
        self.zone_tc.panel_linkable_content_types.set([self.interface_ct])
        self.zone_tc.panel_linkable = False
        self.zone_tc.save(update_fields=["panel_linkable"])
        self.assertFalse(self.zone_tc.is_panel_linkable_for(self.interface_ct.pk))

    def test_queryset_panel_linkable_for_empty_m2m(self):
        qs = TypeConfig.queryset_panel_linkable_for(self.interface_ct.pk)
        self.assertIn(self.zone_tc, qs)
        self.assertIn(self.label_tc, qs)

    def test_queryset_panel_linkable_for_restricted_m2m(self):
        self.zone_tc.panel_linkable_content_types.set([self.interface_ct])
        self.label_tc.panel_linkable_content_types.set([self.prefix_ct])

        iface_qs = TypeConfig.queryset_panel_linkable_for(self.interface_ct.pk)
        self.assertIn(self.zone_tc, iface_qs)
        self.assertNotIn(self.label_tc, iface_qs)

        prefix_qs = TypeConfig.queryset_panel_linkable_for(self.prefix_ct.pk)
        self.assertNotIn(self.zone_tc, prefix_qs)
        self.assertIn(self.label_tc, prefix_qs)

    def test_build_type_choices_filters_by_source_content_type(self):
        self.zone_tc.panel_linkable_content_types.set([self.interface_ct])
        self.label_tc.panel_linkable_content_types.set([self.prefix_ct])

        iface_choices = dict(_build_type_choices(self.interface_ct.pk))
        self.assertIn(self.zone_tc.content_type.pk, iface_choices)
        self.assertNotIn(self.label_tc.content_type.pk, iface_choices)

        prefix_choices = dict(_build_type_choices(self.prefix_ct.pk))
        self.assertNotIn(self.zone_tc.content_type.pk, prefix_choices)
        self.assertIn(self.label_tc.content_type.pk, prefix_choices)

    def test_build_type_choices_skips_panel_linkable_false(self):
        self.zone_tc.panel_linkable = False
        self.zone_tc.save(update_fields=["panel_linkable"])
        choices = dict(_build_type_choices(self.interface_ct.pk))
        self.assertNotIn(self.zone_tc.content_type.pk, choices)
