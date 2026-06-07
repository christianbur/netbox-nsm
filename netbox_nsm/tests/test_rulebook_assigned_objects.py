"""Rulebook Assigned Objects panel (Security Panel links, rulebook-scoped UI)."""

from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory
from django.urls import reverse
from ipam.models import Prefix

from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Site
from netbox_nsm.models import (
    MatchingClassChoices,
    ObjectLink,
    Rulebook,
    RulebookAssignment,
    RulebookTypeChoices,
    TypeConfig,
)
from netbox_nsm.panel_link_actions import object_link_assign_url
from netbox_nsm.rulebook_assigned_objects import build_rulebook_assigned_objects_panel
from netbox_nsm.security_panel_links import build_object_link_rows
from utilities.testing import TestCase


def _device(name):
    site, _ = Site.objects.get_or_create(
        name="NSM Assigned Objects Test Site",
        defaults={"slug": "nsm-assigned-objects-test-site"},
    )
    manufacturer, _ = Manufacturer.objects.get_or_create(
        name="NSM Assigned Objects Test Mfr",
        defaults={"slug": "nsm-assigned-objects-test-mfr"},
    )
    device_type, _ = DeviceType.objects.get_or_create(
        manufacturer=manufacturer,
        model="NSM Assigned Objects Test Model",
        defaults={"slug": "nsm-assigned-objects-test-model"},
    )
    role, _ = DeviceRole.objects.get_or_create(
        name="NSM Assigned Objects Test Role",
        defaults={"slug": "nsm-assigned-objects-test-role"},
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


class BuildObjectLinkRowsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.prefix = Prefix.objects.create(prefix="10.50.0.0/24", status="active")
        cls.zone_tc = TypeConfig.objects.create(
            name="Panel Zone",
            content_type=ContentType.objects.get_for_model(Prefix),
            matching_class=MatchingClassChoices.ZONE,
        )
        cls.device = _device("panel-fw-01")
        cls.iface = Interface.objects.create(
            device=cls.device, name="eth0", type="1000base-t"
        )

    def test_build_object_link_rows_matches_security_panel_links(self):
        ct_iface = ContentType.objects.get_for_model(Interface)
        ct_prefix = ContentType.objects.get_for_model(Prefix)
        ObjectLink.objects.create(
            object_a_type=ct_iface,
            object_a_id=self.iface.pk,
            object_b_type=ct_prefix,
            object_b_id=self.prefix.pk,
        )
        rows = build_object_link_rows(self.iface, "/return/")
        self.assertEqual(len(rows), 1)
        self.assertIn("edit_url", rows[0])
        self.assertIn("delete_url", rows[0])
        self.assertIn("Panel Zone", rows[0]["type_label"])


class RulebookAssignedObjectsPanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="assigned-panel-rb",
            rulebook_type=RulebookTypeChoices.SECURITY_RULES,
        )
        cls.device = _device("assigned-fw-01")
        cls.iface = Interface.objects.create(
            device=cls.device, name="eth0", type="1000base-t"
        )
        cls.prefix = Prefix.objects.create(prefix="10.51.0.0/24", status="active")
        cls.zone_tc = TypeConfig.objects.create(
            name="Assigned Zone",
            content_type=ContentType.objects.get_for_model(Prefix),
            matching_class=MatchingClassChoices.ZONE,
        )
        cls.assignment = RulebookAssignment.objects.create(
            rulebook=cls.rulebook,
            assigned_object_type=ContentType.objects.get_for_model(Device),
            assigned_object_id=cls.device.pk,
        )
        ct_iface = ContentType.objects.get_for_model(Interface)
        ct_prefix = ContentType.objects.get_for_model(Prefix)
        ObjectLink.objects.create(
            object_a_type=ct_iface,
            object_a_id=cls.iface.pk,
            object_b_type=ct_prefix,
            object_b_id=cls.prefix.pk,
        )

    def test_panel_lists_host_interface_and_links(self):
        self.add_permissions("netbox_nsm.add_objectlink")
        request = RequestFactory().get(
            reverse("plugins:netbox_nsm:rulebook", args=[self.rulebook.pk])
        )
        request.user = self.user
        panel = build_rulebook_assigned_objects_panel(self.rulebook, request)
        self.assertFalse(panel["is_empty"])
        self.assertEqual(len(panel["hosts"]), 1)
        host = panel["hosts"][0]
        self.assertEqual(host["host_name"], "assigned-fw-01")
        self.assertEqual(host["host_type_label"], "Device")
        self.assertFalse(host["has_unlinked_interfaces"])
        self.assertEqual(host["linked_interface_count"], 1)
        self.assertTrue(host["interfaces"][0]["has_links"])
        self.assertEqual(len(host["interfaces"]), 1)
        self.assertEqual(host["interfaces"][0]["name"], "eth0")
        self.assertEqual(len(host["interfaces"][0]["link_rows"]), 1)
        self.assertIn("object-link/assign", host["interfaces"][0]["assign_url"])

    def test_panel_marks_unlinked_interfaces_for_filter_toggle(self):
        self.add_permissions("netbox_nsm.add_objectlink")
        Interface.objects.create(
            device=self.device,
            name="eth1",
            type="1000base-t",
        )
        request = RequestFactory().get(
            reverse("plugins:netbox_nsm:rulebook", args=[self.rulebook.pk])
        )
        request.user = self.user
        panel = build_rulebook_assigned_objects_panel(self.rulebook, request)
        host = panel["hosts"][0]
        self.assertEqual(len(host["interfaces"]), 2)
        self.assertTrue(host["has_unlinked_interfaces"])
        self.assertEqual(host["linked_interface_count"], 1)
        linked = [row for row in host["interfaces"] if row["has_links"]]
        unlinked = [row for row in host["interfaces"] if not row["has_links"]]
        self.assertEqual(len(linked), 1)
        self.assertEqual(len(unlinked), 1)
        self.assertEqual(linked[0]["name"], "eth0")
        self.assertEqual(unlinked[0]["name"], "eth1")

    def test_rulebook_detail_renders_assigned_objects_panel(self):
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.view_rulebookassignment",
            "netbox_nsm.add_rulebookassignment",
            "netbox_nsm.delete_rulebookassignment",
            "netbox_nsm.add_objectlink",
        )
        url = reverse("plugins:netbox_nsm:rulebook", args=[self.rulebook.pk])
        content = self.client.get(url).content.decode()
        self.assertIn("Enforcement targets", content)
        self.assertIn("assigned-fw-01", content)
        self.assertIn("eth0", content)
        self.assertIn(
            reverse("plugins:netbox_nsm:rulebook_bulk_assign", args=[self.rulebook.pk]),
            content,
        )
        self.assertNotIn('<th scope="row">Assigned Objects</th>', content)

    def test_rulebook_bulk_assign_get_renders_form(self):
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.add_rulebookassignment")
        url = reverse("plugins:netbox_nsm:rulebook_bulk_assign", args=[self.rulebook.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Assign Policy to Multiple Devices", content)
        self.assertIn(self.rulebook.name, content)

    def test_rulebook_bulk_assign_post_creates_assignment(self):
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.add_rulebookassignment")
        extra_device = _device("assigned-fw-02")
        url = reverse("plugins:netbox_nsm:rulebook_bulk_assign", args=[self.rulebook.pk])
        response = self.client.post(
            url,
            {"devices": [extra_device.pk]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            RulebookAssignment.objects.filter(
                rulebook=self.rulebook,
                assigned_object_id=extra_device.pk,
            ).exists()
        )

    def test_object_link_assign_url_uses_same_endpoint_as_security_panel(self):
        self.add_permissions("netbox_nsm.add_objectlink")
        request = RequestFactory().get("/")
        request.user = self.user
        panel = build_rulebook_assigned_objects_panel(self.rulebook, request)
        iface = panel["hosts"][0]["interfaces"][0]
        expected = object_link_assign_url(self.iface, request.path)
        self.assertEqual(iface["assign_url"].split("?")[0], expected.split("?")[0])
