"""Tests for generic host Security tab URL routing (Approach B)."""

from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from netbox_nsm.security.tab.host_routes import (
    apply_host_security_url_patches,
    host_security_viewname,
)


class HostSecurityRouteTests(SimpleTestCase):
    def test_host_security_viewname(self):
        self.assertEqual(host_security_viewname(), "plugins:netbox_nsm:host_security")

    @override_settings(BASE_PATH="")
    def test_get_action_url_routes_device_security_to_host_url(self):
        apply_host_security_url_patches()

        from dcim.models import Device
        from utilities.views import get_action_url

        url = get_action_url(Device, action="security", kwargs={"pk": 42})
        self.assertEqual(
            url,
            "/plugins/netbox-nsm/security/dcim/device/42/",
        )

    @override_settings(BASE_PATH="")
    def test_get_action_url_defers_custom_object_to_model_hook(self):
        apply_host_security_url_patches()

        try:
            from netbox_custom_objects.models import CustomObject
        except ImportError:
            self.skipTest("netbox-custom-objects not installed")

        with patch.object(
            CustomObject,
            "_get_action_url",
            return_value="/custom/security/",
        ) as mock_co:
            from utilities.views import get_action_url

            url = get_action_url(
                CustomObject,
                action="security",
                kwargs={"pk": 1},
            )

        self.assertEqual(url, "/custom/security/")
        mock_co.assert_called_once()

    @override_settings(BASE_PATH="")
    def test_patch_is_idempotent(self):
        apply_host_security_url_patches()
        import utilities.views as utilities_views

        first = utilities_views.get_action_url
        apply_host_security_url_patches()
        self.assertIs(utilities_views.get_action_url, first)
