"""Tests for IPAM → nsm_address Object Builder."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.objects.address_object_builder import (
    SyncIssue,
    apply_sync_fixes,
    expand_bulk_fix_tokens,
    build_name,
    build_preview_rows,
    create_addresses,
    index_addresses_by_ipam_key,
    ipam_key_for_address,
    is_buildable_ipam_status,
    is_ignored_ipam_status,
    map_status,
    scan_sync_state,
)
from netbox_nsm.objects.object_builder_config import BUILDER_IGNORE_STATUS
from netbox_nsm.objects.nsm_config import (
    format_nsm_config_comment_yaml,
    parse_nsm_config_from_comments,
)
from utilities.testing import TestCase


class ObjectBuilderConfigParseTests(TestCase):
    def test_format_and_parse_object_builder_block(self):
        config = {
            "sort_order": 12,
            "display_template": "{name}",
            "object_builder": {
                "enabled": True,
                "status_map": {"active": "active", "dhcp": BUILDER_IGNORE_STATUS},
                "sources": {
                    "ipam.ipaddress": {
                        "build_template": "H-{host}",
                        "copy_description": True,
                    },
                    "ipam.prefix": {"build_template": "N-{network}-{prefix_length}"},
                    "ipam.iprange": {
                        "build_template": "R-{start_host}-{end_host}"
                    },
                },
            },
        }
        yaml_text = format_nsm_config_comment_yaml(config)
        self.assertIn("object_builder:", yaml_text)
        parsed = parse_nsm_config_from_comments(yaml_text)
        self.assertTrue(parsed["object_builder"]["enabled"])
        self.assertEqual(
            parsed["object_builder"]["sources"]["ipam.ipaddress"]["build_template"],
            "H-{host}",
        )


class BuildNameTests(SimpleTestCase):
    def test_ipaddress_template(self):
        ip = SimpleNamespace(address="10.0.0.1/32", dns_name="host1")
        self.assertEqual(
            build_name(ip, "ipam.ipaddress", "H-{host}"),
            "H-10.0.0.1",
        )
        self.assertEqual(
            build_name(ip, "ipam.ipaddress", "H-{address}"),
            "H-10.0.0.1/32",
        )

    def test_ipaddress_host_placeholder_strips_cidr(self):
        ip = SimpleNamespace(address="172.16.0.1/24")
        self.assertEqual(
            build_name(ip, "ipam.ipaddress", "H-{host}"),
            "H-172.16.0.1",
        )

    def test_prefix_computed_fields(self):
        prefix = SimpleNamespace(prefix="10.1.0.0/24")
        self.assertEqual(
            build_name(prefix, "ipam.prefix", "N-{network}-{prefix_length}"),
            "N-10.1.0.0-24",
        )

    def test_prefix_default_template_uses_hyphen_not_slash(self):
        from netbox_nsm.objects.object_builder_config import DEFAULT_OBJECT_BUILDER_CONFIG

        prefix = SimpleNamespace(prefix="10.112.152.0/28")
        template = DEFAULT_OBJECT_BUILDER_CONFIG["sources"]["ipam.prefix"]["build_template"]
        self.assertEqual(build_name(prefix, "ipam.prefix", template), "N-10.112.152.0-28")

    def test_iprange_template(self):
        ip_range = SimpleNamespace(
            start_address="10.2.0.10/32",
            end_address="10.2.0.20/32",
        )
        self.assertEqual(
            build_name(ip_range, "ipam.iprange", "R-{start_host}-{end_host}"),
            "R-10.2.0.10-10.2.0.20",
        )


class MapStatusTests(SimpleTestCase):
    def test_maps_known_and_default(self):
        status_map = {
            "active": "active",
            "dhcp": BUILDER_IGNORE_STATUS,
            "deprecated": "deprecated",
        }
        self.assertEqual(map_status("dhcp", status_map), BUILDER_IGNORE_STATUS)
        self.assertTrue(is_ignored_ipam_status("dhcp", status_map))
        self.assertFalse(is_ignored_ipam_status("active", status_map))
        self.assertTrue(is_buildable_ipam_status("active", status_map))
        self.assertFalse(is_buildable_ipam_status("reserved", status_map))
        self.assertFalse(is_buildable_ipam_status("deprecated", status_map))
        self.assertFalse(is_buildable_ipam_status("dhcp", status_map))
        self.assertEqual(map_status("unknown", status_map), "active")


class IpamKeyIndexTests(SimpleTestCase):
    def test_index_polymorphic_address(self):
        addr_a = SimpleNamespace(
            address_content_type_id=10,
            address_object_id=5,
        )
        addr_b = SimpleNamespace(
            address_content_type_id=10,
            address_object_id=5,
            name="other",
        )
        index = index_addresses_by_ipam_key([addr_a, addr_b])
        self.assertEqual(len(index[(10, 5)]), 2)

    def test_ipam_key_for_address_prefers_polymorphic(self):
        addr = SimpleNamespace(
            address_content_type_id=3,
            address_object_id=9,
            prefix_id=1,
            prefix=SimpleNamespace(pk=1),
        )
        self.assertEqual(ipam_key_for_address(addr), (3, 9))


class IgnoredStatusBuildTests(SimpleTestCase):
    @patch(
        "netbox_nsm.objects.address_object_builder.ipam_key_for_ipam_obj",
        side_effect=lambda obj: (10, obj.pk),
    )
    @patch("netbox_nsm.objects.address_object_builder._iter_ipam_objects")
    def test_build_preview_skips_ignored_status(self, iter_ipam, _ipam_key):
        dhcp_ip = SimpleNamespace(pk=1, status="dhcp")
        active_ip = SimpleNamespace(pk=2, status="active", address="10.0.0.1/32")
        iter_ipam.return_value = [
            ("ipam.ipaddress", dhcp_ip),
            ("ipam.ipaddress", active_ip),
        ]

        rows = build_preview_rows(
            {
                "enabled": True,
                "status_map": {
                    "active": "active",
                    "dhcp": BUILDER_IGNORE_STATUS,
                },
                "sources": {
                    "ipam.ipaddress": {"build_template": "H-{address}"},
                },
            },
            addr_index={},
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].ipam_obj, active_ip)

    @patch(
        "netbox_nsm.objects.address_object_builder.ipam_key_for_ipam_obj",
        side_effect=lambda obj: (10, obj.pk),
    )
    @patch("netbox_nsm.objects.address_object_builder._iter_ipam_objects")
    def test_build_preview_skips_reserved_and_deprecated(self, iter_ipam, _ipam_key):
        reserved_ip = SimpleNamespace(pk=3, status="reserved", address="10.0.0.2/32")
        deprecated_ip = SimpleNamespace(pk=4, status="deprecated", address="10.0.0.3/32")
        active_ip = SimpleNamespace(pk=2, status="active", address="10.0.0.1/32")
        iter_ipam.return_value = [
            ("ipam.ipaddress", reserved_ip),
            ("ipam.ipaddress", deprecated_ip),
            ("ipam.ipaddress", active_ip),
        ]

        rows = build_preview_rows(
            {
                "enabled": True,
                "status_map": {
                    "active": "active",
                    "reserved": "reserved",
                    "deprecated": "deprecated",
                },
                "sources": {
                    "ipam.ipaddress": {"build_template": "H-{address}"},
                },
            },
            addr_index={},
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].ipam_obj, active_ip)


class ScanSyncStateTests(SimpleTestCase):
    @patch("netbox_nsm.objects.address_object_builder._group_model_and_cot")
    @patch("netbox_nsm.objects.address_object_builder._address_model_and_cot")
    @patch("netbox_nsm.objects.address_object_builder._iter_ipam_objects")
    def test_detects_missing_and_duplicate_ipam_link(
        self, iter_ipam, addr_model_cot, group_model_cot
    ):
        ipam = SimpleNamespace(pk=1, status="active")
        iter_ipam.return_value = [("ipam.ipaddress", ipam)]

        addr1 = SimpleNamespace(
            pk=1,
            name="Host-A",
            status="active",
            address_content_type_id=10,
            address_object_id=1,
        )
        addr2 = SimpleNamespace(
            pk=2,
            name="Host-B",
            status="active",
            address_content_type_id=10,
            address_object_id=1,
        )
        addr_qs = MagicMock()
        addr_qs.iterator.return_value = [addr1, addr2]
        addr_model = MagicMock()
        addr_model.objects.all.return_value = addr_qs
        addr_model_cot.return_value = (addr_model, SimpleNamespace(slug="nsm_address"))
        group_model_cot.return_value = (None, None)

        with patch(
            "netbox_nsm.objects.address_object_builder.ipam_key_for_ipam_obj",
            return_value=(10, 1),
        ), patch(
            "netbox_nsm.objects.address_object_builder._ipam_obj_for_key",
            return_value=ipam,
        ):
            summary = scan_sync_state(
                {
                    "enabled": True,
                    "status_map": {"active": "active"},
                    "sources": {
                        "ipam.ipaddress": {"build_template": "H-{address}"},
                    },
                }
            )

        categories = {issue.category for issue in summary.issues}
        self.assertIn("duplicate_ipam_link", categories)
        self.assertNotIn("missing", categories)

    @patch("netbox_nsm.objects.address_object_builder._group_model_and_cot")
    @patch("netbox_nsm.objects.address_object_builder._address_model_and_cot")
    @patch("netbox_nsm.objects.address_object_builder._iter_ipam_objects")
    def test_ignored_status_not_reported_as_missing(
        self, iter_ipam, addr_model_cot, group_model_cot
    ):
        dhcp_ip = SimpleNamespace(pk=1, status="dhcp")
        iter_ipam.return_value = [("ipam.ipaddress", dhcp_ip)]

        addr_model = MagicMock()
        addr_model.objects.all.return_value.iterator.return_value = []
        addr_model_cot.return_value = (addr_model, SimpleNamespace(slug="nsm_address"))
        group_model_cot.return_value = (None, None)

        summary = scan_sync_state(
            {
                "enabled": True,
                "status_map": {
                    "active": "active",
                    "dhcp": BUILDER_IGNORE_STATUS,
                },
                "sources": {
                    "ipam.ipaddress": {"build_template": "H-{address}"},
                },
            }
        )

        self.assertEqual(summary.issues, [])

    @patch("netbox_nsm.objects.address_object_builder._group_model_and_cot")
    @patch("netbox_nsm.objects.address_object_builder._address_model_and_cot")
    @patch("netbox_nsm.objects.address_object_builder._iter_ipam_objects")
    def test_reserved_without_link_reported_as_missing(
        self, iter_ipam, addr_model_cot, group_model_cot
    ):
        reserved_ip = SimpleNamespace(pk=1, status="reserved")
        iter_ipam.return_value = [("ipam.ipaddress", reserved_ip)]

        addr_model = MagicMock()
        addr_model.objects.all.return_value.iterator.return_value = []
        addr_model_cot.return_value = (addr_model, SimpleNamespace(slug="nsm_address"))
        group_model_cot.return_value = (None, None)

        with patch(
            "netbox_nsm.objects.address_object_builder.ipam_key_for_ipam_obj",
            return_value=(10, 1),
        ):
            summary = scan_sync_state(
                {
                    "enabled": True,
                    "status_map": {
                        "active": "active",
                        "reserved": "reserved",
                    },
                    "sources": {
                        "ipam.ipaddress": {"build_template": "H-{address}"},
                    },
                }
            )

        self.assertEqual([issue.category for issue in summary.issues], ["missing"])
        self.assertFalse(summary.issues[0].can_create)


class SyncIssueFixTests(SimpleTestCase):
    def test_fix_actions_for_name_drift(self):
        issue = SyncIssue(
            category="name_drift",
            address_obj=SimpleNamespace(pk=12),
            expected_name="N-10.0.0.0-24",
        )
        tokens = [action["token"] for action in issue.fix_actions]
        labels = [str(action["label"]) for action in issue.fix_actions]
        self.assertEqual(tokens, ["name_drift:rename:12", "name_drift:replace:12"])
        self.assertEqual(labels, ["Rename", "Create new"])
        self.assertEqual(issue.sync_selection_id, "name_drift:12")
        self.assertTrue(issue.has_fix_actions)

    def test_fix_actions_for_missing_when_buildable(self):
        issue = SyncIssue(
            category="missing",
            source_key="ipam.ipaddress",
            ipam_obj=SimpleNamespace(pk=3),
            expected_name="H-10.0.0.1",
            can_create=True,
        )
        self.assertEqual(issue.fix_actions[0]["token"], "missing:ipam.ipaddress:3")
        self.assertEqual(issue.sync_selection_id, "missing:ipam.ipaddress:3")

    def test_fix_actions_none_for_duplicate_link(self):
        issue = SyncIssue(category="duplicate_ipam_link", addresses=[])
        self.assertEqual(issue.fix_actions, [])
        self.assertFalse(issue.has_fix_actions)


class ExpandBulkFixTokensTests(SimpleTestCase):
    def test_expand_rename_for_name_drift_rows(self):
        tokens = expand_bulk_fix_tokens(
            ["name_drift:12", "name_drift:15", "status_mismatch:3"],
            "rename",
        )
        self.assertEqual(
            tokens,
            ["name_drift:rename:12", "name_drift:rename:15"],
        )

    def test_expand_replace_for_name_drift_rows(self):
        tokens = expand_bulk_fix_tokens(["name_drift:7"], "replace")
        self.assertEqual(tokens, ["name_drift:replace:7"])

    def test_expand_create_for_missing_rows(self):
        tokens = expand_bulk_fix_tokens(
            ["missing:ipam.prefix:42"],
            "create",
        )
        self.assertEqual(tokens, ["missing:ipam.prefix:42"])


class ApplySyncFixesTests(TestCase):
    @patch("netbox_nsm.objects.address_object_builder._fix_name_drift")
    def test_apply_sync_fixes_rename(self, fix_name):
        fix_name.return_value = (True, None)
        result = apply_sync_fixes(
            ["name_drift:rename:5"],
            {"enabled": True, "sources": {}, "status_map": {}},
        )
        self.assertEqual(result.fixed, 1)
        fix_name.assert_called_once_with(5, {"enabled": True, "sources": {}, "status_map": {}})

    @patch("netbox_nsm.objects.address_object_builder._fix_name_drift_replace")
    def test_apply_sync_fixes_replace(self, fix_replace):
        fix_replace.return_value = (True, None)
        result = apply_sync_fixes(
            ["name_drift:replace:5"],
            {"enabled": True, "sources": {}, "status_map": {}},
        )
        self.assertEqual(result.fixed, 1)
        fix_replace.assert_called_once_with(
            5, {"enabled": True, "sources": {}, "status_map": {}}
        )

    @patch("netbox_nsm.objects.address_object_builder._fix_name_drift")
    def test_apply_sync_fixes_legacy_rename_token(self, fix_name):
        fix_name.return_value = (True, None)
        result = apply_sync_fixes(
            ["name_drift:5"],
            {"enabled": True, "sources": {}, "status_map": {}},
        )
        self.assertEqual(result.fixed, 1)

    @patch("netbox_nsm.objects.address_object_builder._fix_name_drift")
    def test_apply_sync_fixes_skips_already_fixed(self, fix_name):
        fix_name.return_value = (False, None)
        result = apply_sync_fixes(
            ["name_drift:rename:5"],
            {"enabled": True, "sources": {}, "status_map": {}},
        )
        self.assertEqual(result.fixed, 0)
        self.assertEqual(result.skipped, 1)


class CreateAddressesIdempotentTests(TestCase):
    @patch("netbox_nsm.objects.address_object_builder.index_addresses_by_ipam_key")
    @patch("netbox_nsm.objects.address_object_builder._address_model_and_cot")
    @patch("netbox_nsm.objects.address_object_builder._model_for_source")
    def test_skips_already_linked(self, model_for_source, addr_model_cot, index_by_key):
        ipam = SimpleNamespace(pk=7, status="active", description="")
        model = MagicMock()
        model.objects.filter.return_value.first.return_value = ipam
        model_for_source.return_value = model

        addr_model = MagicMock()
        addr_model_cot.return_value = (addr_model, SimpleNamespace())
        index_by_key.return_value = {(10, 7): [SimpleNamespace(pk=1)]}

        with patch(
            "netbox_nsm.objects.address_object_builder.ipam_key_for_ipam_obj",
            return_value=(10, 7),
        ):
            result = create_addresses(
                [("ipam.ipaddress", 7)],
                {
                    "enabled": True,
                    "status_map": {"active": "active"},
                    "sources": {
                        "ipam.ipaddress": {"build_template": "H-{address}"},
                    },
                },
            )

        self.assertEqual(result.created, 0)
        self.assertEqual(result.skipped, 1)
        addr_model.objects.create.assert_not_called()
