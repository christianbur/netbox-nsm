"""Tests for PLUGINS_CONFIG address / address-group name templates."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from netbox_nsm.objects.address_name_templates import (
    build_ipam_name_context,
    clear_name_template_caches,
    convert_short_syntax_to_jinja,
    infer_group_match_kind,
    normalize_name_template_list,
    render_address_group_name,
    render_ipam_object_name,
    render_template_string,
    resolve_ipam_name_template,
    template_uses_jinja,
)
from netbox_nsm.objects.address_object_builder import build_name


PLUGIN_TEMPLATES = {
    "address_name_templates": [
        {"template": "h-{ipam>ip}", "match": "host"},
        {"template": "H-{ipam>ip}", "match": "ipaddress"},
        {
            "template": "n-{ipam>prefix>network}-{ipam>prefix>cidr}",
            "match": "prefix",
        },
        {"template": "r-{ipam>range>start}-{ipam>range>end}", "match": "range"},
    ],
    "address_group_name_templates": [
        {"template": "g-{nsm>member_count}-hosts", "match": "host_members"},
        {"template": "grp-{nsm>name}", "match": "any"},
    ],
}


def _plugin_config(plugin, key, default=None):
    if plugin != "netbox_nsm":
        return default
    return PLUGIN_TEMPLATES.get(key, default)


@override_settings(
    PLUGINS_CONFIG={
        "netbox_nsm": PLUGIN_TEMPLATES,
    }
)
class AddressNameTemplateTests(SimpleTestCase):
    def setUp(self):
        clear_name_template_caches()
        self.addCleanup(clear_name_template_caches)

    @patch("netbox.plugins.get_plugin_config", side_effect=_plugin_config)
    def test_short_syntax_host(self, _mock):
        ip = SimpleNamespace(address="10.0.0.1/32")
        self.assertEqual(
            render_ipam_object_name(ip, "ipam.ipaddress"),
            "h-10.0.0.1",
        )

    @patch("netbox.plugins.get_plugin_config", side_effect=_plugin_config)
    def test_short_syntax_prefix(self, _mock):
        prefix = SimpleNamespace(prefix="10.112.152.0/28")
        self.assertEqual(
            render_ipam_object_name(prefix, "ipam.prefix"),
            "n-10.112.152.0-28",
        )

    @patch("netbox.plugins.get_plugin_config", side_effect=_plugin_config)
    def test_short_syntax_iprange(self, _mock):
        ip_range = SimpleNamespace(
            start_address="10.2.0.10/32",
            end_address="10.2.0.20/32",
        )
        self.assertEqual(
            render_ipam_object_name(ip_range, "ipam.iprange"),
            "r-10.2.0.10-10.2.0.20",
        )

    @patch("netbox.plugins.get_plugin_config", side_effect=_plugin_config)
    def test_first_matching_template_wins(self, _mock):
        self.assertEqual(resolve_ipam_name_template("ipam.ipaddress"), "h-{ipam>ip}")

    @patch("netbox.plugins.get_plugin_config", side_effect=_plugin_config)
    def test_native_jinja_uppercase(self, _mock):
        ip = SimpleNamespace(address="10.0.0.1/32")
        rendered = render_template_string(
            "H-{{ ipam.ip | upper }}",
            ip,
            "ipam.ipaddress",
        )
        self.assertEqual(rendered, "H-10.0.0.1")

    @patch("netbox.plugins.get_plugin_config", side_effect=_plugin_config)
    def test_object_builder_fallback_when_no_plugin_match(self, _mock):
        prefix = SimpleNamespace(prefix="10.1.0.0/24")
        builder_config = {
            "sources": {
                "ipam.prefix": {"build_template": "N-{network}-{prefix_length}"},
            }
        }
        with patch(
            "netbox.plugins.get_plugin_config",
            side_effect=lambda plugin, key, default=None: [],
        ):
            clear_name_template_caches()
            self.assertEqual(
                render_ipam_object_name(
                    prefix,
                    "ipam.prefix",
                    builder_config=builder_config,
                ),
                "N-10.1.0.0-24",
            )

    @patch("netbox.plugins.get_plugin_config", side_effect=_plugin_config)
    def test_plugin_template_overrides_object_builder(self, _mock):
        ip = SimpleNamespace(address="172.16.0.1/24")
        builder_config = {
            "sources": {
                "ipam.ipaddress": {"build_template": "legacy-{host}"},
            }
        }
        self.assertEqual(
            render_ipam_object_name(
                ip,
                "ipam.ipaddress",
                builder_config=builder_config,
            ),
            "h-172.16.0.1",
        )

    def test_convert_short_syntax(self):
        self.assertEqual(
            convert_short_syntax_to_jinja("h-{ipam>ip}"),
            "h-{{ ipam.ip }}",
        )
        self.assertEqual(
            convert_short_syntax_to_jinja(
                "n-{ipam>prefix>network}-{ipam>prefix>cidr}"
            ),
            "n-{{ ipam.prefix.network }}-{{ ipam.prefix.cidr }}",
        )

    def test_legacy_template_still_uses_build_name(self):
        ip = SimpleNamespace(address="10.0.0.1/32")
        self.assertEqual(
            render_template_string("H-{host}", ip, "ipam.ipaddress"),
            build_name(ip, "ipam.ipaddress", "H-{host}"),
        )

    def test_template_uses_jinja_detection(self):
        self.assertTrue(template_uses_jinja("h-{ipam>ip}"))
        self.assertTrue(template_uses_jinja("{{ ipam.ip }}"))
        self.assertFalse(template_uses_jinja("H-{host}"))

    def test_normalize_name_template_list(self):
        self.assertEqual(
            normalize_name_template_list(
                [
                    "plain",
                    {"template": "x", "match": "host"},
                    {"template": ""},
                    42,
                ]
            ),
            [
                {"template": "plain", "match": "any"},
                {"template": "x", "match": "host"},
            ],
        )

    def test_build_ipam_name_context(self):
        prefix = SimpleNamespace(prefix="10.0.0.0/24", status=SimpleNamespace(value="active"))
        ctx = build_ipam_name_context(prefix, "ipam.prefix")
        self.assertEqual(ctx["ipam"]["prefix"]["network"], "10.0.0.0")
        self.assertEqual(ctx["ipam"]["prefix"]["cidr"], "24")
        self.assertEqual(ctx["network"], "10.0.0.0")
        self.assertEqual(ctx["prefix_length"], "24")


class AddressGroupNameTemplateTests(SimpleTestCase):
    def setUp(self):
        clear_name_template_caches()
        self.addCleanup(clear_name_template_caches)

    @patch("netbox.plugins.get_plugin_config", side_effect=_plugin_config)
    def test_group_host_members_template(self, _mock):
        group = SimpleNamespace(name="old-name", group=None)
        members = [
            SimpleNamespace(name="h1"),
            SimpleNamespace(name="h2"),
        ]
        with patch(
            "netbox_nsm.objects.address_object_builder.ipam_key_for_address",
            return_value=(1, 1),
        ), patch(
            "netbox_nsm.objects.address_object_builder._ipam_obj_for_key",
            return_value=SimpleNamespace(address="10.0.0.1/32"),
        ), patch(
            "netbox_nsm.objects.address_object_builder.source_key_for_ipam_obj",
            return_value="ipam.ipaddress",
        ):
            self.assertEqual(infer_group_match_kind(members), "host_members")
            self.assertEqual(
                render_address_group_name(group, members=members),
                "g-2-hosts",
            )

    @patch("netbox.plugins.get_plugin_config", side_effect=_plugin_config)
    def test_group_any_fallback_template(self, _mock):
        group = SimpleNamespace(name="my-group", group=None)
        self.assertEqual(
            render_address_group_name(group, members=[]),
            "grp-my-group",
        )
