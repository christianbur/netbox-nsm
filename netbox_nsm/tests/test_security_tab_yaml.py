"""Security tab must tolerate free-text IPAM / address comments (e.g. Tufin metadata)."""

from types import SimpleNamespace

from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory
from ipam.models import Prefix

from netbox_nsm.analyzers.ip_analyzer.addr_analyzable import (
    _object_is_addr_analyzable,
    _object_supports_addr_analyzer,
)
from netbox_nsm.security.tab.context import build_security_tab_context, panel_link_payload
from utilities.testing import TestCase

TUFIN_SUBNET = (
    "network-3.65.246.96-29 | TufinType: subnet | TufinID: 1684006"
)


class SecurityTabYamlTests(TestCase):
    def test_prefix_with_tufin_comments_builds_context(self):
        prefix = Prefix.objects.create(
            prefix="3.65.246.96/29",
            status="active",
            comments=TUFIN_SUBNET,
        )
        request = RequestFactory().get(f"/ipam/prefixes/{prefix.pk}/security/")
        request.user = self.user

        context = build_security_tab_context(prefix, request)

        self.assertIsInstance(context, dict)
        self.assertTrue(context["nsm_page_addr_analyzable"])

    def test_panel_link_payload_tolerates_tufin_address_comments(self):
        addr = SimpleNamespace(
            pk=99,
            name="tufin-imported-address",
            comments=TUFIN_SUBNET,
            custom_object_type=SimpleNamespace(slug="nsm_addresses"),
            status=SimpleNamespace(value="active"),
            _meta=SimpleNamespace(
                app_label="netbox_custom_objects",
                model_name="table1model",
            ),
        )
        addr.get_absolute_url = lambda: "/plugins/custom-objects/nsm_addresses/99/"

        ct = ContentType.objects.get(app_label="ipam", model="prefix")
        payload = panel_link_payload(addr, ct, {})

        self.assertFalse(payload["supports_addr_analyzer"])
        self.assertFalse(payload["addr_analyzable"])

    def test_addr_analyzable_checks_ignore_invalid_address_comments(self):
        addr = SimpleNamespace(
            pk=1,
            name="tufin-addr",
            comments=TUFIN_SUBNET,
            custom_object_type=SimpleNamespace(slug="nsm_addresses"),
            _meta=SimpleNamespace(
                app_label="netbox_custom_objects", model_name="table1model"
            ),
        )
        ct = ContentType.objects.get_for_model(Prefix)

        self.assertFalse(_object_supports_addr_analyzer(addr))
        self.assertFalse(_object_is_addr_analyzable(addr, ct.pk + 1000))
