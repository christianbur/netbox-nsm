"""COT rulebook Assigned Objects panel (enforcement targets)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory
from django.urls import reverse
from ipam.models import Prefix

from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Site
from netbox_nsm.models import CotRulebookAssignment, TypeConfig
from netbox_nsm.objects.link_propagation import CotObjectLinkPropagationChoices
from netbox_nsm.objects.object_link_service import create_or_update_links, get_object_link_model
from netbox_nsm.rulebooks.assigned_objects import build_cot_rulebook_assigned_objects_panel
from netbox_nsm.security.panel_link_actions import object_link_assign_url
from utilities.testing import TestCase

COT_SLUG = "nsm_rb_assigned_panel_test"


def _mock_cot(slug=COT_SLUG):
    fields = MagicMock()
    fields.order_by.return_value = []
    return SimpleNamespace(
        slug=slug,
        pk=10,
        name=slug,
        verbose_name="Assigned Panel Test",
        description="",
        fields=fields,
        get_rulebook_type_display=lambda: "Security Rules",
    )


def _device(name):
    site, _ = Site.objects.get_or_create(
        name="NSM COT Assigned Objects Test Site",
        defaults={"slug": "nsm-cot-assigned-objects-test-site"},
    )
    manufacturer, _ = Manufacturer.objects.get_or_create(
        name="NSM COT Assigned Objects Test Mfr",
        defaults={"slug": "nsm-cot-assigned-objects-test-mfr"},
    )
    device_type, _ = DeviceType.objects.get_or_create(
        manufacturer=manufacturer,
        model="NSM COT Assigned Objects Test Model",
        defaults={"slug": "nsm-cot-assigned-objects-test-model"},
    )
    role, _ = DeviceRole.objects.get_or_create(
        name="NSM COT Assigned Objects Test Role",
        defaults={"slug": "nsm-cot-assigned-objects-test-role"},
    )
    device, _ = Device.objects.get_or_create(
        name=name,
        defaults={
            "device_type": device_type,
            "role": role,
            "site": site,
            "status": "active",
        },
    )
    return device


class CotRulebookAssignedObjectsPanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.device = _device("cot-assigned-fw-01")
        cls.iface = Interface.objects.create(
            device=cls.device, name="eth0", type="1000base-t"
        )
        cls.prefix = Prefix.objects.create(prefix="10.52.0.0/24", status="active")
        TypeConfig.objects.create(
            name="COT Assigned Zone",
            content_type=ContentType.objects.get_for_model(Prefix),
        )
        cls.assignment = CotRulebookAssignment.objects.create(
            cot_slug=COT_SLUG,
            assigned_object_type=ContentType.objects.get_for_model(Device),
            assigned_object_id=cls.device.pk,
        )
        ct_iface = ContentType.objects.get_for_model(Interface)
        ct_prefix = ContentType.objects.get_for_model(Prefix)
        if get_object_link_model() is not None:
            create_or_update_links(
                cls.iface,
                cls.prefix,
                cot_propagation=CotObjectLinkPropagationChoices.DIRECT,
            )

    def test_panel_lists_host_interface_and_links(self):
        self.add_permissions("netbox_nsm.add_objectlink")
        request = RequestFactory().get(
            reverse("plugins:netbox_nsm:cot_rulebook", kwargs={"slug": COT_SLUG})
        )
        request.user = self.user
        panel = build_cot_rulebook_assigned_objects_panel(COT_SLUG, request)
        self.assertFalse(panel["is_empty"])
        self.assertEqual(len(panel["hosts"]), 1)
        host = panel["hosts"][0]
        self.assertEqual(host["host_name"], "cot-assigned-fw-01")
        self.assertEqual(host["host_type_label"], "Device")
        self.assertFalse(host["has_unlinked_interfaces"])
        self.assertEqual(host["linked_interface_count"], 1)
        self.assertTrue(host["interfaces"][0]["has_links"])
        self.assertEqual(host["interfaces"][0]["name"], "eth0")
        self.assertIn("object-link/assign", host["interfaces"][0]["assign_url"])

    def test_panel_marks_unlinked_interfaces_for_filter_toggle(self):
        self.add_permissions("netbox_nsm.add_objectlink")
        Interface.objects.create(
            device=self.device,
            name="eth1",
            type="1000base-t",
        )
        request = RequestFactory().get("/")
        request.user = self.user
        panel = build_cot_rulebook_assigned_objects_panel(COT_SLUG, request)
        host = panel["hosts"][0]
        self.assertEqual(len(host["interfaces"]), 2)
        self.assertTrue(host["has_unlinked_interfaces"])
        self.assertEqual(host["linked_interface_count"], 1)

    @patch("netbox_nsm.rulebooks.views.cot.build_virtual_cot_rulebook_with_hierarchy")
    @patch("netbox_nsm.rulebooks.views.cot.get_deployed_cot_rulebook")
    def test_cot_rulebook_bulk_assign_post_creates_assignment(
        self, mock_get_cot, mock_build
    ):
        from netbox_nsm.rulebooks.virtual_cot import VirtualCotRulebook

        cot = _mock_cot()
        mock_get_cot.return_value = cot
        mock_build.return_value = VirtualCotRulebook(cot, rule_count=0)

        extra_device = _device("cot-assigned-fw-02")
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        url = reverse(
            "plugins:netbox_nsm:cot_rulebook_bulk_assign",
            kwargs={"slug": COT_SLUG},
        )
        response = self.client.post(url, {"devices": [extra_device.pk]})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            CotRulebookAssignment.objects.filter(
                cot_slug=COT_SLUG,
                assigned_object_id=extra_device.pk,
            ).exists()
        )

    @patch("netbox_nsm.rulebooks.views.cot.build_virtual_cot_rulebook_with_hierarchy")
    @patch("netbox_nsm.rulebooks.views.cot.get_deployed_cot_rulebook")
    def test_cot_rulebook_detail_renders_assigned_objects_panel(
        self, mock_get_cot, mock_build
    ):
        from netbox_nsm.rulebooks.views.cot import CotRulebookView
        from netbox_nsm.rulebooks.virtual_cot import VirtualCotRulebook

        cot = _mock_cot()
        mock_get_cot.return_value = cot
        mock_build.return_value = VirtualCotRulebook(cot, rule_count=0)

        url = reverse("plugins:netbox_nsm:cot_rulebook", kwargs={"slug": COT_SLUG})
        request = RequestFactory().get(url)
        request.user = self.user
        request.user.is_superuser = True
        response = CotRulebookView.as_view()(request, slug=COT_SLUG)
        content = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Enforcement targets", content)
        self.assertIn("cot-assigned-fw-01", content)
        self.assertIn("eth0", content)
        self.assertIn(
            reverse(
                "plugins:netbox_nsm:cot_rulebook_bulk_assign",
                kwargs={"slug": COT_SLUG},
            ),
            content,
        )
        self.assertIn("nsm-rb-assigned-edit-toggle", content)
        self.assertIn('class="btn btn-sm btn-primary nsm-rb-assigned-edit-only"', content)
        self.assertIn("nsm-copy-fields-schema-btn", content)
        self.assertIn("nsm-fields-schema-yaml-data", content)

    def test_object_link_assign_url_uses_same_endpoint_as_security_panel(self):
        self.add_permissions("netbox_nsm.add_objectlink")
        request = RequestFactory().get("/")
        request.user = self.user
        panel = build_cot_rulebook_assigned_objects_panel(COT_SLUG, request)
        iface = panel["hosts"][0]["interfaces"][0]
        expected = object_link_assign_url(self.iface, request.path)
        self.assertEqual(iface["assign_url"].split("?")[0], expected.split("?")[0])
