"""Tests for netbox-nsm Django system checks."""

from django.test import SimpleTestCase, override_settings

from django.core import checks


class NsmPluginChecksTests(SimpleTestCase):
    @override_settings(
        PLUGINS=[
            "netbox_nsm",
            "netbox_load_balancing",
        ]
    )
    def test_no_load_order_warning_after_generic_host_security_urls(self):
        nsm_warnings = [
            warning
            for warning in checks.run_checks()
            if warning.id.startswith("netbox_nsm.")
        ]
        self.assertEqual(nsm_warnings, [])
