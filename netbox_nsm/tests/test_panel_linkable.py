"""Tests for Security Panel assign picker (nsm_config-backed)."""

from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType

from dcim.models import Device, Interface
from ipam.models import Prefix

from netbox_nsm.forms.object_link import ObjectLinkAssignForm, _build_type_choices
from netbox_nsm.objects.nsm_config import NsmTypeConfig
from utilities.testing import TestCase


class PanelLinkableTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.interface_ct = ContentType.objects.get_for_model(Interface)
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)
        cls.device_ct = ContentType.objects.get_for_model(Device)

        cls.zone_config = NsmTypeConfig(
            slug="nsm_zone",
            content_type_id=cls.prefix_ct.pk,
            name="Test Zones",
            sort_order=10,
        )
        cls.label_config = NsmTypeConfig(
            slug="nsm_label",
            content_type_id=cls.device_ct.pk,
            name="Test Labels",
            sort_order=11,
        )

    def _patch_lookup(self):
        return patch(
            "netbox_nsm.objects.nsm_config.build_nsm_config_lookup",
            return_value={
                self.zone_config.content_type_id: self.zone_config,
                self.label_config.content_type_id: self.label_config,
            },
        )

    def test_build_type_choices_lists_ui_configs(self):
        with self._patch_lookup():
            choices = dict(_build_type_choices())
        self.assertIn(self.zone_config.content_type_id, choices)
        self.assertIn(self.label_config.content_type_id, choices)

    def test_build_type_choices_same_for_any_assigner(self):
        with self._patch_lookup():
            iface_choices = dict(_build_type_choices(self.interface_ct.pk))
            prefix_choices = dict(_build_type_choices(self.prefix_ct.pk))
        self.assertIn(self.zone_config.content_type_id, iface_choices)
        self.assertIn(self.zone_config.content_type_id, prefix_choices)

    def test_form_clean_allows_ui_config_types(self):
        with self._patch_lookup():
            form = ObjectLinkAssignForm(
                data={
                    "object_a_type_id": self.prefix_ct.pk,
                    "object_a_id": 1,
                    "object_b_type": self.zone_config.content_type_id,
                    "propagation": "direct",
                },
            )
        self.assertNotIn("object_b_type", form.errors)
