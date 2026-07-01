"""Tests for the ObjectLink REST API permission layer.

The ``ObjectLinkViewSet`` operates on the dynamic ``nsm_object_link`` Custom
Object Type, so it cannot rely on the stock ``queryset.model`` permission
machinery. ``ObjectLinkPermission`` resolves the required
``netbox_custom_objects.<action>_<model>`` codename via the same
``object_link_permission()`` helper the UI views use; these tests assert that
access is allowed/denied per that permission for list, retrieve and delete.
"""

from django.urls import reverse

from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Site
from ipam.models import Prefix
from utilities.testing import APITestCase

from netbox_nsm.tests.nsm_prerequisites import ensure_nsm_prerequisites
from netbox_nsm.security.links.object_link_service import (
    create_or_update_links,
    get_object_link_model,
)
from netbox_nsm.tests.rulebook_permission_helpers import grant_object_link_perms


class ObjectLinkApiPermissionTests(APITestCase):
    def setUp(self):
        super().setUp()
        try:
            import netbox_custom_objects  # noqa: F401
        except ImportError:
            self.skipTest("netbox-custom-objects not installed")
        ensure_nsm_prerequisites()
        if get_object_link_model() is None:
            self.skipTest("nsm_object_link COT is not deployed")

        site = Site.objects.create(name="OL API Site", slug="ol-api-site")
        manufacturer = Manufacturer.objects.create(name="OL API Mfr", slug="ol-api-mfr")
        device_type = DeviceType.objects.create(
            manufacturer=manufacturer, model="OL API Model", slug="ol-api-model"
        )
        role = DeviceRole.objects.create(name="OL API Role", slug="ol-api-role")
        self.device = Device.objects.create(
            name="ol-api-device",
            device_type=device_type,
            role=role,
            site=site,
            status="active",
        )
        self.prefix = Prefix.objects.create(prefix="10.77.0.0/24", status="active")
        record, _created = create_or_update_links(
            self.device, self.prefix, cot_propagation="direct", comment="api-test"
        )
        self.link = record.instance

    def _list_url(self):
        return reverse("plugins-api:netbox_nsm-api:objectlink-list")

    def _detail_url(self, pk):
        return reverse(
            "plugins-api:netbox_nsm-api:objectlink-detail", kwargs={"pk": pk}
        )

    @staticmethod
    def _results(response):
        data = response.data
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        return data

    # --- list ------------------------------------------------------------- #
    def test_list_denied_without_permission(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(self._list_url())
        self.assertEqual(response.status_code, 403)

    def test_list_allowed_with_view_permission(self):
        grant_object_link_perms(self, view=True, add=False)
        self.client.force_authenticate(self.user)
        response = self.client.get(self._list_url())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any(row["id"] == self.link.pk for row in self._results(response))
        )

    # --- retrieve --------------------------------------------------------- #
    def test_retrieve_denied_without_permission(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(self._detail_url(self.link.pk))
        self.assertEqual(response.status_code, 403)

    def test_retrieve_allowed_with_view_permission(self):
        grant_object_link_perms(self, view=True, add=False)
        self.client.force_authenticate(self.user)
        response = self.client.get(self._detail_url(self.link.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.link.pk)
        self.assertEqual(response.data["comment"], "api-test")

    # --- delete ----------------------------------------------------------- #
    def test_delete_denied_with_only_view_permission(self):
        grant_object_link_perms(self, view=True, add=False)
        self.client.force_authenticate(self.user)
        response = self.client.delete(self._detail_url(self.link.pk))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            get_object_link_model().objects.filter(pk=self.link.pk).exists()
        )

    def test_delete_allowed_with_delete_permission(self):
        grant_object_link_perms(self, view=True, add=False, delete=True)
        self.client.force_authenticate(self.user)
        response = self.client.delete(self._detail_url(self.link.pk))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            get_object_link_model().objects.filter(pk=self.link.pk).exists()
        )

    # --- unauthenticated -------------------------------------------------- #
    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(self._list_url())
        self.assertIn(response.status_code, (401, 403))
        self.assertNotEqual(response.status_code, 200)
