"""Tests for address analyzability helpers."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils import (
    _object_is_addr_analyzable,
    _object_supports_addr_analyzer,
)
from netbox_nsm.addresses.address_literal import format_network_nsm_config_comments

class ObjectIsAddrAnalyzableTests(SimpleTestCase):
    def test_nsm_object_requires_address_content_type(self):
        addr = MagicMock()
        addr.comments = None
        addr.network_literal = None
        addr._meta.app_label = "netbox_custom_objects"
        addr._meta.model_name = "table1model"
        address_ct_ids = {42}
        self.assertFalse(_object_is_addr_analyzable(addr, 42, address_ct_ids))

    @patch(
        "netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._object_supports_addr_analyzer", return_value=True
    )
    def test_true_for_address_content_type(self, _supports):
        prefix = MagicMock()
        address_ct_ids = {7}
        self.assertTrue(_object_is_addr_analyzable(prefix, 7, address_ct_ids))

    def test_ipam_prefix_analyzable_without_typeconfig(self):
        prefix = MagicMock()
        prefix._meta.app_label = "ipam"
        prefix._meta.model_name = "prefix"
        self.assertTrue(_object_supports_addr_analyzer(prefix))
        self.assertTrue(_object_is_addr_analyzable(prefix, 14, {}))

    @patch("netbox_nsm.analyzers.ip_analyzer.addr_analyzable._hub._addr_is_group_container", return_value=False)
    @patch("netbox_nsm.analyzers.ip_analyzer.addr_analyzable._hub._addr_ip_ref", return_value=None)
    def test_literal_any_address_supports_addr_analyzer(self, _ip_ref, _group):
        obj = MagicMock()
        obj.comments = format_network_nsm_config_comments("0.0.0.0/0").rstrip()
        self.assertTrue(_object_supports_addr_analyzer(obj))
        self.assertTrue(_object_is_addr_analyzable(obj, 275, {275}))

    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils.content_type_ids_for_cot_slugs")
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._object_supports_addr_analyzer",
        return_value=True,
    )
    def test_builds_address_ct_ids_when_none(self, _supports, ct_ids_fn):
        ct_ids_fn.return_value = {42}
        addr = MagicMock()
        self.assertTrue(_object_is_addr_analyzable(addr, 42))
        ct_ids_fn.assert_called_once_with(
            ["nsm_address", "nsm_address_custom", "nsm_address_group"]
        )


