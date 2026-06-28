"""Tests for address tree and IPAM drilldown helpers."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.analysis.addr_analysis_utils import (
    _ADDR_IPAM_FK_FIELDS_SUBNET,
    _addr_ip_ref,
    _addr_ip_ref_field_order,
    _addr_tree_node_display_count,
    _build_addr_tree_node,
    _build_ipam_category_nodes,
    _build_multi_object_addr_analysis,
    _collect_ipam_prefix_children,
    _collect_ipam_prefix_children_impl,
    _count_addr_tree_duplicates,
    _count_ipa_object_tree_duplicates,
    _display_count_for_addr_nodes,
    _enrich_addr_tree_leaf_counts,
    _filter_non_contained_addr_nodes,
    _flatten_ipam_grouped,
    _ipa_object_tree_type_counts,
    _ipam_fk_object_for_addr_node,
    _ipam_stats_ip_count,
    _ipam_stats_range_count,
    _ipam_stats_subnet_count,
    _ipam_stats_total,
    _ipam_stats_short,
    _mark_contained_addr_duplicate_flags,
    _ordered_ipam_stats,
    _prefix_ipam_stats,
    _prefix_is_large,
    _resolve_ipam_stats_from_ip_ref,
    _resolve_summary_type_counts,
    _type_counts_for_addr_nodes,
)

class IpamPrefixTreeTests(SimpleTestCase):
    @patch("netbox_nsm.analysis.addr_analysis_utils._build_ipam_prefix_layer_node")
    @patch("netbox_nsm.analysis.addr_analysis_utils._collect_ipam_prefix_drilldown")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_is_group_container", return_value=False)
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref")
    def test_nsm_address_prefix_only_expands_ipam_drilldown(
        self, ip_ref_fn, _group_container, prefix_drilldown_fn, layer_node_fn
    ):
        from ipam.models import Prefix

        addr = MagicMock()
        addr.pk = 99
        addr.name = "bench-net-demo"
        addr.get_absolute_url.return_value = "/custom-objects/99/"

        prefix = MagicMock(spec=Prefix)
        prefix.pk = 5
        prefix.__str__ = lambda self: "198.18.93.0/24"
        prefix.get_absolute_url.return_value = "/ipam/prefixes/5/"

        ip = MagicMock()
        ip.pk = 7
        ip.__str__ = lambda self: "198.18.93.1/32"
        ip._meta.app_label = "ipam"
        ip._meta.model_name = "ipaddress"
        ip.get_absolute_url.return_value = "/ipam/ip-addresses/7/"

        ip_ref_fn.side_effect = lambda obj: (
            {
                "str": "198.18.93.0/24",
                "url": "/ipam/prefixes/5/",
                "type": "Prefix",
                "ct": 14,
                "pk": 5,
            }
            if getattr(obj, "name", None) == "bench-net-demo"
            else None
        )
        prefix_drilldown_fn.return_value = (
            {
                "child_prefixes": [],
                "ip_addresses": [ip],
                "ip_ranges": [],
                "nsm_addresses": [],
            },
            {
                "ip_addresses": {
                    "kind": "ip_addresses",
                    "label": "IPAM > IP Addresses",
                    "count": 1,
                    "url": "/i/",
                },
            },
            {},
        )
        layer_node_fn.return_value = {
            "name": "198.18.93.0/24",
            "kind": "group",
            "layer": "ipam_prefix",
            "children": [
                {
                    "name": "198.18.93.1/32",
                    "kind": "leaf",
                    "children": [],
                }
            ],
        }

        with patch(
            "netbox_nsm.analysis.addr_analysis_utils._ipam_obj_from_ip_ref",
            return_value=prefix,
        ):
            with patch(
                "netbox_nsm.analysis.addr_analysis_utils._attach_addr_navigation_refs",
                side_effect=lambda node, **kw: node,
            ):
                with patch(
                    "netbox_nsm.analysis.addr_analysis_utils._attach_addr_node_prefix_display",
                    side_effect=lambda node, **kw: node,
                ):
                    node = _build_addr_tree_node(addr)

        self.assertEqual(node["kind"], "group")
        self.assertEqual(node["name"], "bench-net-demo")
        self.assertEqual(node["ip_ref"]["ct"], 14)
        self.assertEqual(len(node["children"]), 1)
        self.assertEqual(node["children"][0]["layer"], "ipam_prefix")
        layer_node_fn.assert_called_once_with(prefix, {addr.pk})

    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analysis.addr_analysis_utils._collect_ipam_prefix_drilldown")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_is_group_container", return_value=False)
    def test_nsm_address_with_host_ip_stays_leaf_without_prefix_drilldown(
        self, _group_container, prefix_drilldown_fn, content_type_cls
    ):
        ct = MagicMock()
        ct.pk = 14
        content_type_cls.objects.get_for_model.return_value = ct

        addr = MagicMock()
        addr.pk = 99
        addr.name = "bench-ip-0018231"
        addr.get_absolute_url.return_value = "/custom-objects/99/"
        addr.range = None

        prefix = MagicMock()
        prefix.pk = 5
        prefix.__str__ = lambda self: "198.18.182.0/24"
        prefix.get_absolute_url.return_value = "/ipam/prefixes/5/"

        ip = MagicMock()
        ip.pk = 7
        ip.__str__ = lambda self: "198.18.182.32/32"
        ip.get_absolute_url.return_value = "/ipam/ip-addresses/7/"

        addr.prefix = prefix
        addr.ip_address = ip

        prefix_drilldown_fn.side_effect = AssertionError(
            "prefix drilldown must not run when host ip_address is set"
        )

        with patch(
            "netbox_nsm.analysis.addr_analysis_utils._ipam_obj_from_ip_ref",
            return_value=ip,
        ):
            with patch(
                "netbox_nsm.analysis.addr_analysis_utils._attach_addr_navigation_refs",
                side_effect=lambda node, **kw: node,
            ):
                with patch(
                    "netbox_nsm.analysis.addr_analysis_utils._attach_addr_node_prefix_display",
                    side_effect=lambda node, **kw: node,
                ):
                    node = _build_addr_tree_node(addr)

        self.assertEqual(node["kind"], "leaf")
        self.assertEqual(node["name"], "bench-ip-0018231")
        self.assertEqual(node["ip_ref"]["str"], "198.18.182.32/32")
        self.assertEqual(node["children"], [])

    @patch("django.contrib.contenttypes.models.ContentType")
    def test_addr_ip_ref_prefers_host_ip_over_parent_prefix(self, content_type_cls):
        from netbox_nsm.analysis.addr_analysis_utils import (
            _ADDR_IPAM_FK_FIELDS_SUBNET,
            _addr_ip_ref,
            _addr_ip_ref_field_order,
            _ipam_fk_object_for_addr_node,
        )

        ct = MagicMock()
        ct.pk = 21
        content_type_cls.objects.get_for_model.return_value = ct

        addr = MagicMock()
        addr.prefix = MagicMock()
        addr.prefix.__str__ = lambda self: "198.18.182.0/24"
        addr.prefix.get_absolute_url.return_value = "/ipam/prefixes/5/"
        addr.prefix.pk = 5

        addr.ip_address = MagicMock()
        addr.ip_address.__str__ = lambda self: "198.18.182.32/32"
        addr.ip_address.get_absolute_url.return_value = "/ipam/ip-addresses/7/"
        addr.ip_address.pk = 7
        addr.range = None

        self.assertEqual(_addr_ip_ref_field_order(addr), ("ip_address", "range", "prefix"))
        self.assertEqual(_addr_ip_ref_field_order(MagicMock(prefix=addr.prefix, ip_address=None, range=None)), _ADDR_IPAM_FK_FIELDS_SUBNET)
        self.assertIs(_ipam_fk_object_for_addr_node(addr), addr.ip_address)

        ip_ref = _addr_ip_ref(addr)
        self.assertEqual(ip_ref["str"], "198.18.182.32/32")
        self.assertEqual(ip_ref["type"], "IP Address")
        self.assertEqual(ip_ref["pk"], 7)

    @patch("netbox_nsm.objects.address_ipam_fk.iter_address_ipam_fk_refs")
    def test_addr_ip_ref_falls_back_to_polymorphic_gfk(self, iter_refs_fn):
        from netbox_nsm.analysis.addr_analysis_utils import (
            _addr_ip_ref,
            _ipam_fk_object_for_addr_node,
        )

        prefix = MagicMock()
        prefix.__str__ = lambda self: "10.112.146.0/24"
        prefix.get_absolute_url.return_value = "/ipam/prefixes/25/"
        prefix.pk = 25

        ipam_ct = MagicMock()
        ipam_ct.pk = 70

        fk_ref = MagicMock()
        fk_ref.ipam_obj = prefix
        fk_ref.ipam_ct = ipam_ct
        fk_ref.field_name = "address"
        iter_refs_fn.return_value = [fk_ref]

        addr = MagicMock()
        addr.prefix = None
        addr.ip_address = None
        addr.range = None

        ip_ref = _addr_ip_ref(addr)
        self.assertEqual(ip_ref["str"], "10.112.146.0/24")
        self.assertEqual(ip_ref["type"], "Address")
        self.assertEqual(ip_ref["pk"], 25)
        self.assertIs(_ipam_fk_object_for_addr_node(addr), prefix)

    @patch("netbox_nsm.analysis.addr_analysis_utils._object_supports_addr_analysis", return_value=True)
    @patch("netbox_nsm.analysis.addr_analysis_utils._build_ipam_prefix_layer_node")
    @patch("netbox_nsm.analysis.addr_analysis_utils._collect_ipam_prefix_drilldown")
    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_addr_navigation_refs", side_effect=lambda node, **kw: node)
    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_addr_node_prefix_display", side_effect=lambda node, **kw: node)
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_is_group_container", return_value=False)
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref")
    def test_nsm_address_prefix_uses_two_layer_structure(
        self,
        ip_ref_fn,
        _group_container,
        _pfx_display,
        _nav_refs,
        prefix_drilldown_fn,
        layer_node_fn,
        _supports_fn,
    ):
        from ipam.models import Prefix

        prefix = MagicMock(spec=Prefix)
        prefix.pk = 5
        prefix.prefix = "10.245.10.0/24"
        prefix.__str__ = lambda self: "10.245.10.0/24"
        prefix.get_absolute_url.return_value = "/ipam/prefixes/5/"

        addr = MagicMock()
        addr.pk = 10
        addr.name = "demo-addr-0010"
        addr.get_absolute_url.return_value = "/custom-objects/10/"

        ip_ref_fn.side_effect = lambda obj: (
            {
                "str": "10.245.10.0/24",
                "url": "/ipam/prefixes/5/",
                "type": "Prefix",
                "ct": 14,
                "pk": 5,
            }
            if getattr(obj, "name", None) == "demo-addr-0010"
            else None
        )
        prefix_drilldown_fn.return_value = (
            {
                "child_prefixes": [],
                "ip_addresses": [],
                "ip_ranges": [],
                "nsm_addresses": [],
            },
            {
                "ip_addresses": {
                    "kind": "ip_addresses",
                    "label": "IPAM > IP Addresses",
                    "count": 1,
                    "url": "/i/",
                },
            },
            {},
        )
        layer_node_fn.return_value = {
            "name": "10.245.10.0/24",
            "kind": "group",
            "layer": "ipam_prefix",
            "ipam_stats": _ordered_ipam_stats({"ip_addresses": {"count": 1}}),
            "children": [
                {
                    "name": "10.245.10.1/32",
                    "kind": "leaf",
                    "ip_ref": {"str": "10.245.10.1/32", "type": "IP Address"},
                    "children": [],
                }
            ],
        }

        with patch(
            "netbox_nsm.analysis.addr_analysis_utils._ipam_obj_from_ip_ref",
            return_value=prefix,
        ):
            node = _build_addr_tree_node(addr)

            self.assertIsNotNone(node)
            self.assertEqual(node["kind"], "group")
            self.assertEqual(node["name"], "demo-addr-0010")
            self.assertEqual(len(node["children"]), 1)
            self.assertEqual(node["children"][0]["layer"], "ipam_prefix")
            self.assertEqual(node["children"][0]["name"], "10.245.10.0/24")
            layer_node_fn.assert_called_once_with(prefix, {addr.pk})

            analysis = _build_multi_object_addr_analysis([addr])
            self.assertEqual(analysis[0]["types"][0]["count_subnets"], 1)
            self.assertEqual(analysis[0]["types"][0]["count_ips"], 1)
            self.assertEqual(analysis[0]["types"][0]["leaf_count"], 2)

    @patch("netbox_nsm.objects.address_ipam_fk.addresses_for_ipam_object_queryset")
    @patch("netbox_nsm.analysis.addr_analysis_utils._prefix_ipam_stats")
    @patch("netbox_nsm.objects.address_ipam_fk.get_nsm_address_model")
    def test_collect_ipam_prefix_children_queries_all_kinds(
        self, addr_model_fn, stats_fn, addr_qs_fn
    ):
        prefix = MagicMock()
        prefix.pk = 5
        prefix.prefix = "10.245.10.0/24"

        child_prefix = MagicMock()
        ip = MagicMock()
        rng = MagicMock()
        addr = MagicMock()

        prefix.get_child_prefixes.return_value.order_by.return_value.__getitem__.return_value = [
            child_prefix
        ]
        prefix.get_child_ips.return_value.order_by.return_value.__getitem__.return_value = [
            ip
        ]
        prefix.get_child_ranges.return_value.order_by.return_value.__getitem__.return_value = [
            rng
        ]

        stats_fn.return_value = {
            "child_prefixes": {"count": 1, "label": "Child Prefixes", "url": "/p/"},
            "ip_addresses": {"count": 1, "label": "IP Addresses", "url": "/i/"},
            "ip_ranges": {"count": 1, "label": "IP Ranges", "url": "/r/"},
        }

        addr_model = MagicMock()
        addr_filter = MagicMock()
        addr_filter.count.return_value = 1
        addr_filter.order_by.return_value.__getitem__.return_value = [addr]
        addr_model_fn.return_value = addr_model
        addr_qs_fn.return_value = addr_filter

        grouped, stats, truncated = _collect_ipam_prefix_children_impl(prefix)

        self.assertEqual(
            _flatten_ipam_grouped(grouped), [child_prefix, ip, rng, addr]
        )
        self.assertEqual(stats["child_prefixes"]["count"], 1)
        self.assertFalse(any(truncated.values()))

    def test_ordered_ipam_stats_keeps_netbox_tab_order(self):
        stats = {
            "ip_ranges": {"label": "IPAM > IP Ranges", "count": 3},
            "child_prefixes": {"label": "IPAM > Prefixes", "count": 1},
            "ip_addresses": {"label": "IPAM > IP Addresses", "count": 2},
        }
        ordered = _ordered_ipam_stats(stats)
        self.assertEqual(
            [item["label"] for item in ordered],
            ["IPAM > Prefixes", "IPAM > IP Addresses", "IPAM > IP Ranges"],
        )

    def test_ipam_stats_short_format(self):
        ordered = _ordered_ipam_stats(
            {
                "child_prefixes": {"count": 0},
                "ip_addresses": {"count": 100},
                "ip_ranges": {"count": 0},
                "nsm_addresses": {"count": 101},
            }
        )
        self.assertEqual(_ipam_stats_short(ordered), "0/100/0/101")

    def test_ipam_stats_total_sums_pill_segments(self):
        ordered = _ordered_ipam_stats(
            {
                "child_prefixes": {"count": 2068},
                "ip_addresses": {"count": 200000},
                "ip_ranges": {"count": 0},
                "nsm_addresses": {"count": 1},
            }
        )
        self.assertEqual(_ipam_stats_total(ordered), 202069)

    def test_ipam_stats_ip_count_reads_ip_addresses_segment(self):
        ordered = _ordered_ipam_stats(
            {
                "child_prefixes": {"count": 2068},
                "ip_addresses": {"count": 200000},
                "ip_ranges": {"count": 0},
                "nsm_addresses": {"count": 1},
            }
        )
        self.assertEqual(_ipam_stats_ip_count(ordered), 200000)

    @patch("netbox_nsm.analysis.ipam_drilldown._prefix_ipam_stats")
    @patch("netbox_nsm.analysis.ipam_drilldown._lookup_ipam_prefix_from_ip_ref")
    def test_resolve_ipam_stats_from_ip_ref_without_type_uses_lookup(
        self, lookup_fn, stats_fn
    ):
        lookup_fn.return_value = MagicMock()
        stats_fn.return_value = {"ip_addresses": {"count": 42}}
        stats = _resolve_ipam_stats_from_ip_ref(
            {"ct": 14, "pk": 1, "str": "10.0.0.0/8"}
        )
        self.assertEqual(stats["ip_addresses"]["count"], 42)

    def test_display_count_uses_ipam_stats_on_group(self):
        node = {
            "kind": "group",
            "name": "n-10.0.0.0/8",
            "ipam_stats": _ordered_ipam_stats(
                {
                    "child_prefixes": {"count": 2068},
                    "ip_addresses": {"count": 200000},
                    "ip_ranges": {"count": 0},
                    "nsm_addresses": {"count": 1},
                }
            ),
            "children": [{"kind": "category", "count": 2068, "children": []}],
        }
        _enrich_addr_tree_leaf_counts(node)
        self.assertEqual(node["leaf_count"], 200000)
        self.assertEqual(_addr_tree_node_display_count(node), 202069)
        self.assertEqual(_display_count_for_addr_nodes([node]), 200000)

    def test_type_counts_from_ipam_stats_on_group(self):
        node = {
            "kind": "group",
            "name": "g-10.0.0.0/8",
            "ipam_stats": _ordered_ipam_stats(
                {
                    "child_prefixes": {"count": 1},
                    "ip_addresses": {"count": 50000},
                    "ip_ranges": {"count": 0},
                }
            ),
            "children": [],
        }
        counts = _type_counts_for_addr_nodes([node])
        self.assertEqual(counts["count_subnets"], 1)
        self.assertEqual(counts["count_ranges"], 0)
        self.assertEqual(counts["count_ips"], 50000)

    def test_type_counts_from_loaded_tree_categories(self):
        node = {
            "kind": "group",
            "name": "n-10.245.10.0/24",
            "ip_ref": {"str": "10.245.10.0/24", "type": "Prefix"},
            "children": [
                {
                    "kind": "category",
                    "name": "IPAM > Prefixes",
                    "count": 2,
                    "children": [],
                },
                {
                    "kind": "category",
                    "name": "IPAM > IP Addresses",
                    "count": 5,
                    "children": [],
                },
                {
                    "kind": "category",
                    "name": "IPAM > IP Ranges",
                    "count": 1,
                    "children": [],
                },
            ],
        }
        counts = _type_counts_for_addr_nodes([node])
        self.assertEqual(counts["count_subnets"], 2)
        self.assertEqual(counts["count_ranges"], 1)
        self.assertEqual(counts["count_ips"], 5)

    def test_type_counts_excludes_contained_prefix_roots(self):
        bench = {
            "kind": "group",
            "name": "bench-ip-0009313",
            "ip_ref": {"str": "198.18.93.0/24", "url": "/ipam/prefixes/1/", "type": "Prefix"},
            "ipam_stats": _ordered_ipam_stats({"ip_addresses": {"count": 100}}),
            "children": [],
        }
        slash8 = {
            "kind": "group",
            "name": "n-10.0.0.0/8",
            "ip_ref": {"str": "10.0.0.0/8", "url": "/ipam/prefixes/99/", "type": "Prefix"},
            "ipam_stats": _ordered_ipam_stats(
                {
                    "child_prefixes": {"count": 1},
                    "ip_addresses": {"count": 50000},
                    "ip_ranges": {"count": 0},
                }
            ),
            "children": [],
        }
        counts = _type_counts_for_addr_nodes([bench, slash8])
        self.assertEqual(counts["count_subnets"], 1)
        self.assertEqual(counts["count_ranges"], 0)
        self.assertEqual(counts["count_ips"], 50000)

    def test_ipam_stats_subnet_and_range_count_helpers(self):
        ordered = _ordered_ipam_stats(
            {
                "child_prefixes": {"count": 3},
                "ip_addresses": {"count": 10},
                "ip_ranges": {"count": 2},
            }
        )
        self.assertEqual(_ipam_stats_subnet_count(ordered), 3)
        self.assertEqual(_ipam_stats_range_count(ordered), 2)
        self.assertEqual(_ipam_stats_ip_count(ordered), 10)

    @patch("netbox_nsm.analysis.addr_analysis_utils._object_supports_addr_analysis", return_value=True)
    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_nodes",
        return_value=([], ["all,line"]),
    )
    def test_build_multi_object_addr_analysis_includes_type_counts(
        self, build_nodes_fn, supports_fn
    ):
        node = {
            "kind": "group",
            "name": "g-10.0.0.0/8",
            "ipam_stats": _ordered_ipam_stats(
                {
                    "child_prefixes": {"count": 1},
                    "ip_addresses": {"count": 50000},
                    "ip_ranges": {"count": 0},
                }
            ),
            "children": [],
        }
        build_nodes_fn.return_value = ([node], ["all,line"])
        analysis = _build_multi_object_addr_analysis([MagicMock()])
        type_block = analysis[0]["types"][0]
        self.assertEqual(type_block["count_subnets"], 1)
        self.assertEqual(type_block["count_ranges"], 0)
        self.assertEqual(type_block["count_ips"], 50000)
        self.assertEqual(type_block["leaf_count"], 50001)

    def test_resolve_summary_type_counts_falls_back_to_object_tree(self):
        object_tree = [
            {
                "name": "g-10.0.0.0/8",
                "kind": "group",
                "children": [
                    {
                        "name": "n-10.1.0.0/16",
                        "kind": "leaf",
                        "children": [],
                        "ip_ref": {"str": "10.1.0.0/16", "type": "Prefix"},
                    }
                ],
            },
            {
                "name": "host-a",
                "kind": "leaf",
                "children": [],
                "ip_ref": {"str": "10.0.0.1/32", "type": "IP Address"},
            },
        ]
        counts = _resolve_summary_type_counts([], object_tree)
        self.assertEqual(counts["count_subnets"], 2)
        self.assertEqual(counts["count_ranges"], 0)
        self.assertEqual(counts["count_ips"], 1)

    def test_ipa_object_tree_type_counts(self):
        object_tree = [
            {
                "name": "range-a",
                "kind": "leaf",
                "children": [],
                "ip_ref": {"str": "10.0.0.1-10.0.0.10", "type": "Range"},
                "ipam_stats": _ordered_ipam_stats(
                    {"ip_addresses": {"count": 10, "label": "IP Addresses", "url": "#"}}
                ),
            },
            {
                "name": "prefix-a",
                "kind": "leaf",
                "children": [],
                "ip_ref": {"str": "10.1.0.0/16", "type": "Prefix"},
                "ipam_stats": _ordered_ipam_stats(
                    {
                        "child_prefixes": {"count": 0, "label": "Prefixes", "url": "#"},
                        "ip_addresses": {"count": 5, "label": "IP Addresses", "url": "#"},
                        "ip_ranges": {"count": 0, "label": "IP Ranges", "url": "#"},
                    }
                ),
            },
        ]
        counts = _ipa_object_tree_type_counts(object_tree)
        self.assertEqual(counts["count_subnets"], 1)
        self.assertEqual(counts["count_ranges"], 0)
        self.assertEqual(counts["count_ips"], 0)

    @patch("netbox_nsm.analysis.addr_analysis_utils._ipam_obj_from_ip_ref")
    def test_ipa_object_tree_type_counts_uses_unique_ipam_ips(self, ipam_obj_fn):
        def fake_ipam_obj(model_name, pk):
            obj = MagicMock()
            obj.pk = pk
            obj._meta.app_label = "ipam"
            obj._meta.model_name = model_name
            return obj

        ip_a = fake_ipam_obj("ipaddress", 101)
        ip_b = fake_ipam_obj("ipaddress", 102)
        ip_c = fake_ipam_obj("ipaddress", 103)
        prefix_a = fake_ipam_obj("prefix", 1)
        prefix_b = fake_ipam_obj("prefix", 2)
        prefix_a.get_child_ips.return_value = [ip_a, ip_b]
        prefix_b.get_child_ips.return_value = [ip_b, ip_c]
        ipam_obj_fn.side_effect = lambda ref: {
            1: prefix_a,
            2: prefix_b,
        }.get(int(ref.get("pk") or 0))

        object_tree = [
            {
                "name": "prefix-a",
                "kind": "leaf",
                "children": [],
                "prefix_display_cidr": "10.0.0.0/24",
                "ip_ref": {"str": "10.0.0.0/24", "type": "Prefix", "ct": 99, "pk": 1},
            },
            {
                "name": "prefix-b",
                "kind": "leaf",
                "children": [],
                "prefix_display_cidr": "10.0.1.0/24",
                "ip_ref": {"str": "10.0.1.0/24", "type": "Prefix", "ct": 99, "pk": 2},
            },
        ]

        counts = _ipa_object_tree_type_counts(object_tree)

        self.assertEqual(counts["count_subnets"], 2)
        self.assertEqual(counts["count_ranges"], 0)
        self.assertEqual(counts["count_ips"], 3)

    def test_ipa_object_tree_type_counts_cell_prefix_with_zero_child_stats(self):
        object_tree = [
            {
                "name": "dm-addr-10-112-129-0-24",
                "kind": "group",
                "is_cell_direct": True,
                "prefix_display_cidr": "10.112.129.0/24",
                "node_role": "nsm_prefix",
                "children": [],
                "ipam_stats": _ordered_ipam_stats(
                    {
                        "child_prefixes": {"count": 0, "label": "Prefixes", "url": "#"},
                        "ip_addresses": {"count": 0, "label": "IP Addresses", "url": "#"},
                        "ip_ranges": {"count": 0, "label": "IP Ranges", "url": "#"},
                    }
                ),
            },
            {
                "name": "dm-addr-10-112-134-0-24",
                "kind": "group",
                "is_cell_direct": True,
                "prefix_display_cidr": "10.112.134.0/24",
                "node_role": "nsm_prefix",
                "children": [
                    {
                        "name": "h-10.112.134.44",
                        "kind": "leaf",
                        "prefix_display_cidr": "10.112.134.44/32",
                        "subnet_contained_in": "10.112.134.0/24",
                        "children": [],
                    }
                ],
                "ipam_stats": _ordered_ipam_stats(
                    {
                        "child_prefixes": {"count": 0, "label": "Prefixes", "url": "#"},
                        "ip_addresses": {"count": 1, "label": "IP Addresses", "url": "#"},
                        "ip_ranges": {"count": 0, "label": "IP Ranges", "url": "#"},
                    }
                ),
            },
        ]
        counts = _ipa_object_tree_type_counts(object_tree)
        self.assertEqual(counts["count_subnets"], 2)
        self.assertEqual(counts["count_ips"], 1)

    def test_mark_contained_addr_duplicate_flags(self):
        bench = {
            "kind": "group",
            "name": "bench-ip-0009313",
            "ip_ref": {"str": "198.18.93.0/24", "url": "/ipam/prefixes/1/", "type": "Prefix"},
            "children": [],
        }
        slash8 = {
            "kind": "group",
            "name": "n-10.0.0.0/8",
            "url": "/ipam/prefixes/99/",
            "ip_ref": {"str": "10.0.0.0/8", "url": "/ipam/prefixes/99/", "type": "Prefix"},
            "children": [],
        }
        nodes = [bench, slash8]
        _mark_contained_addr_duplicate_flags(nodes)
        self.assertTrue(bench.get("count_duplicate"))
        self.assertEqual(bench.get("count_duplicate_of"), "n-10.0.0.0/8")
        self.assertEqual(bench.get("count_duplicate_of_url"), "/ipam/prefixes/99/")
        self.assertNotIn("count_duplicate", slash8)

    def test_count_addr_tree_duplicates(self):
        bench = {
            "kind": "group",
            "name": "bench-ip",
            "count_duplicate": True,
            "children": [],
        }
        slash8 = {
            "kind": "group",
            "name": "n-10.0.0.0/8",
            "children": [],
        }
        self.assertEqual(_count_addr_tree_duplicates([bench, slash8]), 1)

    def test_count_ipa_object_tree_duplicates(self):
        object_tree = [
            {
                "name": "g-10.0.0.0/8",
                "children": [
                    {
                        "name": "bench-a",
                        "subnet_contained_in": "10.0.0.0/8",
                        "children": [],
                    },
                    {
                        "name": "bench-b",
                        "subnet_contained_in": "10.0.0.0/8",
                        "children": [],
                    },
                ],
            },
            {
                "name": "bench-a",
                "is_doppelt": True,
                "children": [],
            },
        ]
        self.assertEqual(_count_ipa_object_tree_duplicates(object_tree), 3)

    def test_resolve_summary_type_counts_merges_object_tree_duplicates(self):
        addr_analysis = [
            {
                "types": [
                    {
                        "count_subnets": 1,
                        "count_ranges": 0,
                        "count_ips": 50000,
                        "nodes": [],
                    }
                ]
            }
        ]
        object_tree = [
            {
                "name": "g-10.0.0.0/8",
                "ipam_stats": _ordered_ipam_stats(
                    {
                        "child_prefixes": {"count": 1},
                        "ip_addresses": {"count": 100},
                        "ip_ranges": {"count": 0},
                    }
                ),
                "children": [
                    {
                        "name": "bench-a",
                        "subnet_contained_in": "10.0.0.0/8",
                        "children": [],
                    }
                ],
            }
        ]
        counts = _resolve_summary_type_counts(addr_analysis, object_tree)
        self.assertEqual(counts["count_ips"], 0)
        self.assertEqual(counts["count_duplicates"], 1)

    @patch("netbox_nsm.objects.address_ipam_fk.get_nsm_address_model", return_value=None)
    @patch("django.urls.reverse", return_value="/ipam/")
    def test_prefix_ipam_stats_uses_get_child_ips_count(self, _reverse_fn, _addr_model_fn):
        prefix = MagicMock()
        prefix.pk = 1
        prefix.get_child_prefixes.return_value.count.return_value = 500
        prefix.get_child_ips.return_value.count.return_value = 50000
        prefix.get_child_ranges.return_value.count.return_value = 0
        stats = _prefix_ipam_stats(prefix)
        self.assertEqual(stats["ip_addresses"]["count"], 50000)
        prefix.get_child_ips.return_value.count.assert_called_once_with()

    def test_type_counts_group_slash8_skips_duplicate_nested_slash8_child(self):
        slash8_stats = _ordered_ipam_stats(
            {
                "child_prefixes": {"count": 500},
                "ip_addresses": {"count": 50000},
                "ip_ranges": {"count": 0},
            }
        )
        nested = {
            "kind": "group",
            "name": "n-10.0.0.0/8",
            "ip_ref": {"str": "10.0.0.0/8", "url": "/ipam/prefixes/99/", "type": "Prefix"},
            "ipam_stats": slash8_stats,
            "children": [],
        }
        group = {
            "kind": "group",
            "name": "g-10.0.0.0/8",
            "ipam_stats": slash8_stats,
            "children": [nested],
        }
        counts = _type_counts_for_addr_nodes([group])
        self.assertEqual(counts["count_ips"], 50000)
        self.assertEqual(counts["count_subnets"], 500)

    def test_type_counts_group_inferred_slash8_uses_nested_prefix_ip_stats(self):
        """g-* group without ipam_stats: nested n-* /8 member supplies IP badge total."""
        slash8_stats = _ordered_ipam_stats(
            {
                "child_prefixes": {"count": 500},
                "ip_addresses": {"count": 50000},
                "ip_ranges": {"count": 0},
            }
        )
        nested = {
            "kind": "group",
            "name": "n-10.0.0.0-8",
            "ip_ref": {"str": "10.0.0.0/8", "url": "/ipam/prefixes/501/", "type": "Prefix"},
            "ipam_stats": slash8_stats,
            "children": [],
        }
        group = {
            "kind": "group",
            "name": "g-10.0.0.0/8",
            "children": [nested],
        }
        counts = _type_counts_for_addr_nodes([group])
        self.assertEqual(counts["count_ips"], 50000)
        self.assertEqual(counts["count_subnets"], 500)

    def test_type_counts_equal_slash8_roots_keep_single_ip_total(self):
        slash8_stats = _ordered_ipam_stats(
            {
                "child_prefixes": {"count": 500},
                "ip_addresses": {"count": 50000},
                "ip_ranges": {"count": 0},
            }
        )
        g_root = {
            "kind": "group",
            "name": "g-10.0.0.0/8",
            "ip_ref": {"str": "10.0.0.0/8", "url": "/ipam/prefixes/1/", "type": "Prefix"},
            "ipam_stats": slash8_stats,
            "children": [],
        }
        n_root = {
            "kind": "group",
            "name": "n-10.0.0.0/8",
            "ip_ref": {"str": "10.0.0.0/8", "url": "/ipam/prefixes/99/", "type": "Prefix"},
            "ipam_stats": slash8_stats,
            "children": [],
        }
        nodes = [g_root, n_root]
        _mark_contained_addr_duplicate_flags(nodes)
        self.assertTrue(n_root.get("count_duplicate"))
        counts = _type_counts_for_addr_nodes(nodes)
        self.assertEqual(counts["count_ips"], 50000)

    def test_type_counts_slash8_parent_excludes_contained_slash24_ips(self):
        """IPs badge uses /8 ipam_stats, not /8 host capacity; /24 roots are excluded."""
        bench = {
            "kind": "group",
            "name": "bench-ip-0009313",
            "ip_ref": {"str": "198.18.93.0/24", "url": "/ipam/prefixes/1/", "type": "Prefix"},
            "ipam_stats": _ordered_ipam_stats({"ip_addresses": {"count": 100}}),
            "children": [],
        }
        slash8 = {
            "kind": "group",
            "name": "n-10.0.0.0/8",
            "ip_ref": {"str": "10.0.0.0/8", "url": "/ipam/prefixes/99/", "type": "Prefix"},
            "ipam_stats": _ordered_ipam_stats(
                {
                    "child_prefixes": {"count": 500},
                    "ip_addresses": {"count": 50000},
                    "ip_ranges": {"count": 0},
                }
            ),
            "children": [],
        }
        counts = _type_counts_for_addr_nodes([bench, slash8])
        self.assertEqual(counts["count_subnets"], 500)
        self.assertEqual(counts["count_ips"], 50000)
        self.assertNotEqual(counts["count_ips"], 16777216)

    def test_display_count_excludes_prefixes_contained_in_another_root(self):
        bench_stats = _ordered_ipam_stats(
            {
                "child_prefixes": {"count": 0},
                "ip_addresses": {"count": 100},
                "ip_ranges": {"count": 0},
                "nsm_addresses": {"count": 101},
            }
        )
        slash8_stats = _ordered_ipam_stats(
            {
                "child_prefixes": {"count": 2068},
                "ip_addresses": {"count": 200000},
                "ip_ranges": {"count": 0},
                "nsm_addresses": {"count": 1},
            }
        )
        bench = {
            "kind": "group",
            "name": "bench-ip-0009313",
            "ip_ref": {"str": "198.18.93.0/24", "url": "/ipam/prefixes/1/", "type": "Prefix"},
            "ipam_stats": bench_stats,
            "children": [],
        }
        slash8 = {
            "kind": "group",
            "name": "n-10.0.0.0/8",
            "ip_ref": {"str": "10.0.0.0/8", "url": "/ipam/prefixes/99/", "type": "Prefix"},
            "ipam_stats": slash8_stats,
            "children": [],
        }
        nodes = [bench, slash8]
        self.assertEqual(_filter_non_contained_addr_nodes(nodes), [slash8])
        self.assertEqual(_display_count_for_addr_nodes(nodes), 200000)

    def test_display_count_keeps_sibling_prefixes(self):
        a = {
            "kind": "group",
            "name": "bench-a",
            "ip_ref": {"str": "198.18.93.0/24", "url": "/p/1/", "type": "Prefix"},
            "ipam_stats": _ordered_ipam_stats({"ip_addresses": {"count": 100}}),
            "children": [],
        }
        b = {
            "kind": "group",
            "name": "bench-b",
            "ip_ref": {"str": "198.19.34.0/24", "url": "/p/2/", "type": "Prefix"},
            "ipam_stats": _ordered_ipam_stats({"ip_addresses": {"count": 100}}),
            "children": [],
        }
        self.assertEqual(len(_filter_non_contained_addr_nodes([a, b])), 2)
        self.assertEqual(_display_count_for_addr_nodes([a, b]), 200)

    def test_prefix_is_large_by_child_count(self):
        stats = {"child_prefixes": {"count": 51}, "ip_addresses": {"count": 0}}
        self.assertTrue(_prefix_is_large(stats))

    def test_prefix_is_large_by_ip_count(self):
        stats = {"child_prefixes": {"count": 1}, "ip_addresses": {"count": 1001}}
        self.assertTrue(_prefix_is_large(stats))

    def test_prefix_not_large_below_thresholds(self):
        stats = {"child_prefixes": {"count": 50}, "ip_addresses": {"count": 1000}}
        self.assertFalse(_prefix_is_large(stats))

    @patch("netbox_nsm.analysis.addr_analysis_utils._prefix_ipam_stats")
    def test_large_prefix_collect_skips_child_queries(self, stats_fn):
        prefix = MagicMock()
        prefix.pk = 99
        stats_fn.return_value = {
            "child_prefixes": {"count": 2068, "label": "IPAM > Prefixes", "url": "/p/"},
            "ip_addresses": {"count": 200000, "label": "IPAM > IP Addresses", "url": "/i/"},
            "ip_ranges": {"count": 0, "label": "IPAM > IP Ranges", "url": "/r/"},
        }

        grouped, stats, truncated = _collect_ipam_prefix_children_impl(prefix)

        prefix.get_child_prefixes.assert_not_called()
        self.assertEqual(grouped["child_prefixes"], [])
        self.assertTrue(truncated["child_prefixes"])
        self.assertTrue(truncated["ip_addresses"])

    @patch("netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_node")
    def test_large_prefix_category_nodes_lazy_only(self, build_node_fn):
        prefix = MagicMock()
        prefix.pk = 99
        stats = {
            "child_prefixes": {"count": 2068, "label": "IPAM > Prefixes", "url": "/p/"},
            "ip_addresses": {"count": 200000, "label": "IPAM > IP Addresses", "url": "/i/"},
            "ip_ranges": {"count": 0, "label": "IPAM > IP Ranges", "url": "/r/"},
        }
        grouped = {
            "child_prefixes": [],
            "ip_addresses": [],
            "ip_ranges": [],
            "nsm_addresses": [],
        }

        nodes = _build_ipam_category_nodes(prefix, grouped, stats, set())

        build_node_fn.assert_not_called()
        self.assertEqual(len(nodes), 3)
        self.assertTrue(nodes[0]["lazy_load"])
        self.assertEqual(nodes[0]["loaded_count"], 0)
        self.assertEqual(nodes[0]["count"], 2068)
        self.assertFalse(nodes[2]["lazy_load"])
        self.assertEqual(nodes[2]["count"], 0)

    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_prefix_ipam_meta", side_effect=lambda n, *a, **k: n)
    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_addr_node_prefix_display", side_effect=lambda n, **k: n)
    @patch("netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_node")
    @patch("netbox_nsm.analysis.addr_analysis_utils._prefix_ipam_stats")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_is_group_container", return_value=False)
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref", return_value=None)
    def test_large_ipam_prefix_tree_is_summary_only(
        self,
        _ip_ref,
        _group_container,
        stats_fn,
        build_node_fn,
        _pfx_display,
        _ipam_meta,
    ):
        prefix = MagicMock()
        prefix.pk = 99
        prefix._meta.app_label = "ipam"
        prefix._meta.model_name = "prefix"
        prefix.__str__ = lambda self: "10.0.0.0/8"
        prefix.get_absolute_url.return_value = "/ipam/prefixes/99/"
        stats_fn.return_value = {
            "child_prefixes": {"count": 2068, "label": "IPAM > Prefixes", "url": "/p/"},
            "ip_addresses": {"count": 200000, "label": "IPAM > IP Addresses", "url": "/i/"},
            "ip_ranges": {"count": 0, "label": "IPAM > IP Ranges", "url": "/r/"},
        }

        node = _build_addr_tree_node(prefix)

        build_node_fn.assert_not_called()
        prefix.get_child_prefixes.assert_not_called()
        self.assertEqual(node["kind"], "group")
        self.assertEqual(len(node["children"]), 2)
        lazy_batches = [c for c in node["children"] if c.get("lazy_load")]
        self.assertEqual(len(lazy_batches), 2)
        self.assertTrue(all(child["lazy_load"] for child in lazy_batches))


class AddrTreeCountingTests(SimpleTestCase):
    def test_prefix_leaf_counts_as_subnet_not_ip(self):
        from netbox_nsm.analysis.addr_analysis_utils import (
            _addr_tree_node_ip_count,
            _addr_tree_node_subnet_count,
            _FIELD_TYPE_LABELS,
        )

        node = {
            "kind": "leaf",
            "ip_ref": {"type": _FIELD_TYPE_LABELS["prefix"], "str": "10.112.129.0/24"},
            "prefix_display_cidr": "10.112.129.0/24",
        }
        self.assertEqual(_addr_tree_node_subnet_count(node), 1)
        self.assertEqual(_addr_tree_node_ip_count(node), 0)

    def test_prefix_group_with_empty_child_stats_counts_as_one_subnet(self):
        from netbox_nsm.analysis.addr_analysis_utils import (
            _addr_tree_node_subnet_count,
            _FIELD_TYPE_LABELS,
            _ordered_ipam_stats,
        )

        node = {
            "kind": "group",
            "ip_ref": {"type": _FIELD_TYPE_LABELS["prefix"], "str": "10.112.129.0/24"},
            "ipam_stats": _ordered_ipam_stats(
                {
                    "child_prefixes": {"count": 0},
                    "ip_addresses": {"count": 0},
                    "ip_ranges": {"count": 0},
                }
            ),
            "children": [],
        }
        self.assertEqual(_addr_tree_node_subnet_count(node), 1)

    def test_filter_ipam_drilldown_drops_nsm_addresses_category(self):
        from netbox_nsm.analysis.addr_analysis_utils import (
            _filter_ipam_drilldown_category_nodes,
        )

        nodes = [
            {
                "kind": "category",
                "name": "IPAM > IP Addresses",
                "lazy_ctx": {"category": "ip_addresses"},
            },
            {
                "kind": "category",
                "name": "COT > Addresses",
                "lazy_ctx": {"category": "nsm_addresses"},
            },
        ]
        filtered = _filter_ipam_drilldown_category_nodes(nodes)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(
            (filtered[0].get("lazy_ctx") or {}).get("category"), "ip_addresses"
        )


class IpamResolveNodesTests(SimpleTestCase):
    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_addr_node_prefix_display", side_effect=lambda n, **k: n)
    @patch("netbox_nsm.analysis.ipam_drilldown._build_ipam_prefix_resolve_nodes")
    @patch("netbox_nsm.analysis.ipam_drilldown._collect_ipam_prefix_children_impl")
    def test_build_ipam_prefix_layer_node_creates_explicit_prefix_layer(
        self, collect_impl, resolve_nodes_fn, _display, content_type_cls
    ):
        from netbox_nsm.analysis.addr_analysis_utils import _build_ipam_prefix_layer_node

        ct = MagicMock()
        ct.pk = 14
        content_type_cls.objects.get_for_model.return_value = ct

        prefix = MagicMock()
        prefix.pk = 42
        prefix.prefix = "10.112.129.0/24"
        prefix.get_absolute_url.return_value = "/ipam/prefixes/42/"

        stats = {
            "child_prefixes": {"count": 0, "label": "IPAM > Prefixes", "url": "/p/"},
            "ip_addresses": {"count": 2, "label": "IPAM > IP Addresses", "url": "/i/"},
            "ip_ranges": {"count": 0, "label": "IPAM > IP Ranges", "url": "/r/"},
        }
        collect_impl.return_value = (
            {"child_prefixes": [], "ip_addresses": [], "ip_ranges": [], "nsm_addresses": []},
            stats,
            {},
        )
        resolve_nodes_fn.return_value = [
            {"name": "10.112.129.1/32", "kind": "leaf", "children": []},
        ]

        node = _build_ipam_prefix_layer_node(prefix, set())

        self.assertEqual(node["name"], "10.112.129.0/24")
        self.assertEqual(node["layer"], "ipam_prefix")
        self.assertEqual(node["kind"], "group")
        self.assertEqual(node["ip_ref"]["type"], "Prefix")
        self.assertEqual(_ipam_stats_ip_count(node["ipam_stats"]), 2)
        self.assertEqual(len(node["children"]), 1)

    @patch("netbox_nsm.analysis._lazy_api._build_addr_tree_node")
    @patch("netbox_nsm.analysis._lazy_api._addr_tree_child_visited", return_value=set())
    @patch("netbox_nsm.analysis.ipam_drilldown._collect_ipam_prefix_children_impl")
    def test_prefix_resolve_expands_nested_prefix_and_ips(
        self, collect_impl, _child_visited, build_node
    ):
        from netbox_nsm.analysis.ipam_drilldown import _build_ipam_prefix_resolve_nodes

        parent = MagicMock()
        parent.pk = 1
        child_prefix = MagicMock()
        child_prefix.pk = 2
        ip_obj = MagicMock()
        ip_obj.pk = 3

        stats = {
            "child_prefixes": {"count": 1, "label": "IPAM > Prefixes", "url": "/p/"},
            "ip_addresses": {"count": 1, "label": "IPAM > IP Addresses", "url": "/i/"},
            "ip_ranges": {"count": 0, "label": "IPAM > IP Ranges", "url": "/r/"},
        }
        collect_impl.return_value = (
            {
                "child_prefixes": [child_prefix],
                "ip_addresses": [ip_obj],
                "ip_ranges": [],
            },
            stats,
            {},
        )
        build_node.side_effect = lambda obj, visited: {
            "name": str(getattr(obj, "pk", obj)),
            "kind": "leaf" if obj is ip_obj else "group",
            "children": [],
        }

        nodes = _build_ipam_prefix_resolve_nodes(parent, set())

        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0]["kind"], "group")
        self.assertEqual(nodes[1]["kind"], "leaf")

    @patch("netbox_nsm.analysis._lazy_api._build_addr_tree_node")
    @patch("netbox_nsm.analysis.ipam_drilldown._collect_ipam_range_ip_children")
    @patch("netbox_nsm.analysis.ipam_drilldown._ipam_range_ip_count", return_value=3)
    def test_range_resolve_uses_ipam_ip_count_for_badge(
        self, ip_count_fn, collect_ips, build_node
    ):
        from netbox_nsm.analysis.ipam_drilldown import _build_ipam_range_resolve_nodes

        ip_range = MagicMock()
        ip_range.pk = 9
        ip_range.start_address = "10.0.0.1"
        ip_range.end_address = "10.0.0.3"
        ip_range.__str__ = lambda self: "10.0.0.1-10.0.0.3"
        ip_range.get_absolute_url.return_value = "/ipam/ip-ranges/9/"

        ip_a = MagicMock()
        collect_ips.return_value = [ip_a]
        build_node.return_value = {
            "name": "10.0.0.1",
            "kind": "leaf",
            "children": [],
        }

        node = _build_ipam_range_resolve_nodes(ip_range, set())

        self.assertEqual(node["kind"], "group")
        self.assertEqual(
            _hub_import_ip_count(node),
            3,
        )
        self.assertEqual(len(node["children"]), 2)
        self.assertEqual(node["children"][0]["kind"], "leaf")
        self.assertEqual(node["children"][1]["kind"], "lazy_batch")


class AddrTreeDuplicateTests(SimpleTestCase):
    def test_contained_prefix_marked_duplicate_and_excluded_from_ip_count(self):
        from netbox_nsm.analysis.addr_analysis_utils import (
            _addr_tree_node_ip_count,
            _addr_tree_node_subnet_count,
            _mark_contained_addr_duplicate_flags,
            _type_counts_for_addr_nodes,
        )

        slash8 = {
            "name": "g-10.0.0.0/8",
            "kind": "group",
            "ip_ref": {"str": "10.0.0.0/8", "type": "Prefix"},
            "ipam_stats": [
                {"kind": "ip_addresses", "count": 100},
            ],
            "children": [],
        }
        slash16 = {
            "name": "n-10.1.0.0/16",
            "kind": "group",
            "ip_ref": {"str": "10.1.0.0/16", "type": "Prefix"},
            "ipam_stats": [
                {"kind": "ip_addresses", "count": 50},
            ],
            "children": [],
        }
        roots = [slash8, slash16]
        _mark_contained_addr_duplicate_flags(roots)

        self.assertTrue(slash16.get("count_duplicate"))
        self.assertEqual(slash16.get("count_duplicate_of"), "g-10.0.0.0/8")
        self.assertEqual(_addr_tree_node_ip_count(slash16), 0)

        counts = _type_counts_for_addr_nodes(roots)
        self.assertEqual(counts["count_ips"], 100)
        self.assertEqual(counts["count_subnets"], 1)
        self.assertEqual(_addr_tree_node_subnet_count(slash16), 0)


def _hub_import_ip_count(node):
    from netbox_nsm.analysis.addr_analysis_utils import _ipam_stats_ip_count

    return _ipam_stats_ip_count(node.get("ipam_stats") or [])


class LookupIpamPrefixForCidrTests(SimpleTestCase):
    @patch("ipam.models.Prefix.objects")
    def test_lookup_uses_netaddr_ipnetwork(self, prefix_mgr):
        from netaddr import IPNetwork

        from netbox_nsm.analysis.addr_diff_collect import _lookup_ipam_prefix_for_cidr

        prefix_mgr.filter.return_value.order_by.return_value.first.return_value = (
            MagicMock()
        )
        _lookup_ipam_prefix_for_cidr("198.18.228.0/24")
        prefix_mgr.filter.assert_called_once_with(prefix=IPNetwork("198.18.228.0/24"))


from utilities.testing import TestCase


class LookupIpamPrefixForCidrIntegrationTests(TestCase):
    def test_lookup_resolves_existing_prefix(self):
        from ipam.models import Prefix

        from netbox_nsm.analysis.addr_diff_collect import _lookup_ipam_prefix_for_cidr
        from netbox_nsm.analysis.ipam_drilldown import _resolve_ipam_stats_from_ip_ref

        prefix = Prefix.objects.create(prefix="198.18.228.0/24", status="active")
        found = _lookup_ipam_prefix_for_cidr("198.18.228.0/24")
        self.assertIsNotNone(found)
        self.assertEqual(found.pk, prefix.pk)

        stats = _resolve_ipam_stats_from_ip_ref({"str": "198.18.228.0/24"})
        self.assertIsNotNone(stats)
        self.assertIn("ip_addresses", stats)

