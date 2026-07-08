"""Tests for Security tab eligibility (Object A/B)."""

from django.contrib.contenttypes.models import ContentType

from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Rack, Site

from netbox_nsm.security.tab.eligibility import (
    clear_object_link_eligibility_cache,
    get_object_link_allowed_content_type_ids,
    is_security_tab_eligible,
)
from netbox_nsm.tests.nsm_prerequisites import ensure_nsm_prerequisites
from utilities.testing import TestCase


class SecurityTabEligibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        try:
            import netbox_custom_objects  # noqa: F401
        except ImportError:
            return
        ensure_nsm_prerequisites()
        cls.site = Site.objects.create(name="Elig Site", slug="elig-site")
        manufacturer = Manufacturer.objects.create(name="Elig Mfr", slug="elig-mfr")
        device_type = DeviceType.objects.create(
            manufacturer=manufacturer,
            model="Elig Model",
            slug="elig-model",
        )
        role = DeviceRole.objects.create(name="Elig Role", slug="elig-role")
        cls.device = Device.objects.create(
            name="elig-device",
            device_type=device_type,
            role=role,
            site=cls.site,
            status="active",
        )
        cls.rack = Rack.objects.create(name="elig-rack", site=cls.site, status="active")

    def setUp(self):
        clear_object_link_eligibility_cache()

    def test_host_and_security_ids_populated_when_schema_deployed(self):
        try:
            import netbox_custom_objects  # noqa: F401
        except ImportError:
            self.skipTest("netbox_custom_objects not installed")
        host_ids, security_ids = get_object_link_allowed_content_type_ids()
        if not host_ids and not security_ids:
            self.skipTest("nsm_object_link schema not deployed")
        self.assertTrue(host_ids)
        self.assertTrue(security_ids)

    def test_device_is_eligible_when_in_host_types(self):
        try:
            import netbox_custom_objects  # noqa: F401
        except ImportError:
            self.skipTest("netbox_custom_objects not installed")
        if not hasattr(self, "device"):
            self.skipTest("prerequisites not created")
        host_ids, _security_ids = get_object_link_allowed_content_type_ids()
        if not host_ids:
            self.skipTest("nsm_object_link schema not deployed")
        device_ct = ContentType.objects.get_for_model(Device)
        if device_ct.pk not in host_ids:
            self.skipTest("device not configured as Object A in this install")
        self.assertTrue(is_security_tab_eligible(self.device))

    def test_rack_not_eligible_when_not_in_schema(self):
        try:
            import netbox_custom_objects  # noqa: F401
        except ImportError:
            self.skipTest("netbox_custom_objects not installed")
        if not hasattr(self, "rack"):
            self.skipTest("prerequisites not created")
        host_ids, security_ids = get_object_link_allowed_content_type_ids()
        if not host_ids and not security_ids:
            self.skipTest("nsm_object_link schema not deployed")
        rack_ct = ContentType.objects.get_for_model(Rack)
        if rack_ct.pk in host_ids or rack_ct.pk in security_ids:
            self.skipTest("rack is configured as Object A/B in this install")
        self.assertFalse(is_security_tab_eligible(self.rack))
