"""COT rulebook Assigned Objects panel (enforcement points)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory
from django.urls import reverse
from ipam.models import Prefix

from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Site
from netbox_nsm.forms import EnforcementPointInterfaceAssignForm
from netbox_nsm.objects.object_link_service import (
    LINK_TYPE_ENFORCEMENT_POINT,
    create_or_update_enforcement_point_link,
    create_or_update_links,
    find_enforcement_point_iface_link,
    find_enforcement_point_host_link,
    get_object_link_model,
)
from netbox_nsm.rulebooks.assigned_objects import build_cot_rulebook_assigned_objects_panel
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
        if get_object_link_model() is not None:
            create_or_update_enforcement_point_link(cls.device, COT_SLUG)
            create_or_update_enforcement_point_link(
                cls.iface,
                COT_SLUG,
                policy_object=cls.prefix,
            )

    def test_panel_lists_host_interface_and_enforcement_point_links(self):
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
        self.assertIn("enforcement-point/assign", host["interfaces"][0]["assign_url"])

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

    def test_policy_link_does_not_count_as_enforcement_point_interface_link(self):
        self.add_permissions("netbox_nsm.add_objectlink")
        device = _device("cot-assigned-fw-policy-only")
        iface = Interface.objects.create(
            device=device, name="eth0", type="1000base-t"
        )
        if get_object_link_model() is not None:
            create_or_update_enforcement_point_link(device, COT_SLUG)
            create_or_update_links(iface, self.prefix, cot_propagation="direct")

        request = RequestFactory().get("/")
        request.user = self.user
        panel = build_cot_rulebook_assigned_objects_panel(COT_SLUG, request)
        host = next(h for h in panel["hosts"] if h["host_name"] == "cot-assigned-fw-policy-only")
        self.assertEqual(host["linked_interface_count"], 0)
        self.assertFalse(host["interfaces"][0]["has_links"])

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
        if get_object_link_model() is not None:
            link = find_enforcement_point_host_link(extra_device, COT_SLUG)
            self.assertIsNotNone(link)
            self.assertEqual(
                getattr(link.instance, "link_type", None),
                LINK_TYPE_ENFORCEMENT_POINT,
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

    def test_panel_builds_without_prefetch_related_exception(self):
        self.add_permissions("netbox_nsm.add_objectlink")
        request = RequestFactory().get("/")
        request.user = self.user
        with patch(
            "django.db.models.prefetch_related_objects",
            side_effect=ValueError("prefetch should not be called"),
        ):
            panel = build_cot_rulebook_assigned_objects_panel(COT_SLUG, request)
        self.assertFalse(panel["is_empty"])

    def test_enforcement_point_assign_url_uses_dedicated_endpoint(self):
        self.add_permissions("netbox_nsm.add_objectlink")
        device = _device("cot-assigned-fw-assign-url")
        Interface.objects.create(
            device=device, name="eth0", type="1000base-t"
        )
        if get_object_link_model() is not None:
            create_or_update_enforcement_point_link(device, COT_SLUG)

        request = RequestFactory().get("/")
        request.user = self.user
        panel = build_cot_rulebook_assigned_objects_panel(COT_SLUG, request)
        host = next(h for h in panel["hosts"] if h["host_name"] == "cot-assigned-fw-assign-url")
        iface_row = host["interfaces"][0]
        expected = reverse(
            "plugins:netbox_nsm:enforcement_point_link_assign",
            kwargs={"slug": COT_SLUG},
        )
        self.assertIn(expected, iface_row["assign_url"])

    def test_enforcement_point_interface_assign_form_valid_without_propagation(self):
        iface_ct = ContentType.objects.get_for_model(self.iface)
        prefix_ct = ContentType.objects.get_for_model(self.prefix)
        form = EnforcementPointInterfaceAssignForm(
            {
                "object_a_type_id": str(iface_ct.pk),
                "object_a_id": str(self.iface.pk),
                "object_b_type": str(prefix_ct.pk),
            },
            source_object=self.iface,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_enforcement_point_interface_assign_post_creates_link(self):
        if get_object_link_model() is None:
            self.skipTest("nsm_object_link COT is not deployed")
        self.add_permissions("netbox_nsm.add_objectlink")
        device = _device("cot-assign-post-fw")
        iface = Interface.objects.create(
            device=device, name="eth0", type="1000base-t"
        )
        prefix = Prefix.objects.create(prefix="10.54.0.0/24", status="active")
        create_or_update_enforcement_point_link(device, COT_SLUG)
        url = reverse(
            "plugins:netbox_nsm:enforcement_point_link_assign",
            kwargs={"slug": COT_SLUG},
        )
        iface_ct = ContentType.objects.get_for_model(iface)
        prefix_ct = ContentType.objects.get_for_model(prefix)
        response = self.client.post(
            url,
            {
                "object_a_type_id": iface_ct.pk,
                "object_a_id": iface.pk,
                "object_b_type": prefix_ct.pk,
                "object_b_id": prefix.pk,
                "return_url": "/",
                "comment": "via assign view",
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        link = find_enforcement_point_iface_link(iface, prefix, COT_SLUG)
        self.assertIsNotNone(link)
        self.assertEqual(link.comment, "via assign view")
