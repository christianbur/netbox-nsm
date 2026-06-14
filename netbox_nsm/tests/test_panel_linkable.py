"""Tests for Security Panel assign picker (nsm_config-backed)."""

from contextlib import contextmanager
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

    def _panel_configs(self):
        return [self.zone_config, self.label_config]

    @contextmanager
    def _patch_lookup(self):
        configs = self._panel_configs()
        with patch(
            "netbox_nsm.forms.object_link.filter_assignable_configs",
            return_value=configs,
        ), patch(
            "netbox_nsm.forms.object_link.iter_panel_linkable_configs",
            return_value=configs,
        ):
            yield

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
        prefix = Prefix.objects.create(prefix="10.62.0.0/24", status="active")
        with self._patch_lookup(), patch(
            "netbox_nsm.forms.object_link.is_assignable_from_content_type",
            return_value=True,
        ):
            form = ObjectLinkAssignForm(
                data={
                    "object_a_type_id": self.prefix_ct.pk,
                    "object_a_id": prefix.pk,
                    "object_b_type": str(self.zone_config.content_type_id),
                    "propagation": "direct",
                },
                source_object=prefix,
            )
            self.assertTrue(form.is_valid(), form.errors)
