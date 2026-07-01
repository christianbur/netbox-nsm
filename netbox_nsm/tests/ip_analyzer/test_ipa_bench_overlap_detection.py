"""Verify IPA detects overlap-bucket naming patterns used in address demo bundles."""

from __future__ import annotations

import ipaddress
from collections import Counter
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils import (
    _build_ipa_cell_object_tree,
    _build_multi_object_addr_analyzer,
    _count_addr_tree_duplicates,
    _count_ipa_object_tree_duplicates,
    _count_ipa_object_tree_group_duplicates,
    _mark_contained_addr_duplicate_flags,
)
from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import IPA_TREE_NODE_INFO_GAP
from netbox_nsm.tests.fixtures.ipa_bench_overlap_naming import (
    BENCH_OVERLAP_SHOWCASE_RULE_COUNT,
    HOSTS_PER_SUBNET,
    OVERLAP_ALIAS_STRIDE,
    OVERLAP_DEMO_RULE_COUNT,
    OVERLAP_DUP_NAME_STRIDE,
    PREFIX_LEN_SUPER,
    PREFIX_LEN_WIDE,
    _alias_comments,
    _alias_name,
    _alias_stride_for_leaf,
    _dup_name,
    _host_cidr,
    _leaf_in_overlap_bucket,
    _leaf_name,
    _overlap_bucket_leaf_count,
    _overlap_bucket_subnet_count,
    _subnet_prefix_cidr,
    _super_name,
    _wide_name,
    _wider_prefix_cidr,
    overlap_demo_rule_descriptions,
)


def _walk_nodes(nodes):
    for node in nodes or []:
        yield node
        yield from _walk_nodes(node.get("children") or [])


def _collect_flagged(nodes, flag):
    return [n for n in _walk_nodes(nodes) if n.get(flag)]


class BenchOverlapExpectationTests(SimpleTestCase):
    """Expected overlap volume from bench generator formulas."""

    def test_overlap_demo_rules_documented_for_manual_ui_testing(self):
        descriptions = overlap_demo_rule_descriptions()
        self.assertEqual(len(descriptions), BENCH_OVERLAP_SHOWCASE_RULE_COUNT)
        self.assertEqual(OVERLAP_DEMO_RULE_COUNT, BENCH_OVERLAP_SHOWCASE_RULE_COUNT)
        names = {row["name"] for row in descriptions}
        self.assertEqual(
            names,
            {f"bench-rule-{i:05d}" for i in range(1, BENCH_OVERLAP_SHOWCASE_RULE_COUNT + 1)},
        )

    def test_overlap_bucket_counts_at_1000_and_1500_leaves(self):
        self.assertEqual(_overlap_bucket_leaf_count(1000), 75)
        self.assertEqual(_overlap_bucket_subnet_count(1000), 1)
        self.assertEqual(_overlap_bucket_leaf_count(1500), 112)
        self.assertEqual(_overlap_bucket_subnet_count(1500), 2)

    def test_overlap_alias_and_dup_indices_in_bucket(self):
        limit = _overlap_bucket_leaf_count(1000)
        alias_leaves = [
            i
            for i in range(limit)
            if i % _alias_stride_for_leaf(i, limit) == 0
        ]
        dup_leaves = [
            i
            for i in range(limit)
            if _leaf_in_overlap_bucket(i, limit)
            and i % OVERLAP_DUP_NAME_STRIDE == 0
        ]
        self.assertGreater(len(alias_leaves), 10)
        self.assertGreater(len(dup_leaves), 10)
        self.assertEqual(alias_leaves[0], 0)
        self.assertEqual(dup_leaves[0], 0)
        self.assertLess(OVERLAP_ALIAS_STRIDE, 8)

    def test_bench_containment_cidrs_for_overlap_subnet(self):
        host = _host_cidr(0, 0)
        net24 = _subnet_prefix_cidr(0)
        net20 = _wider_prefix_cidr(0, PREFIX_LEN_WIDE)
        net16 = _wider_prefix_cidr(0, PREFIX_LEN_SUPER)
        host_net = ipaddress.ip_network(host, strict=False)
        self.assertTrue(host_net.subnet_of(ipaddress.ip_network(net24)))
        self.assertTrue(host_net.subnet_of(ipaddress.ip_network(net20)))
        self.assertTrue(host_net.subnet_of(ipaddress.ip_network(net16)))


class BenchOverlapIpaDetectionTests(SimpleTestCase):
    """IPA builders must surface each bench overlap mechanism."""

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ip_meta")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members", return_value=[])
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref")
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_alias_peer_same_ipam_merged_as_cell_addresses_multi(
        self, content_type_cls, ip_ref_fn, _members_fn, attach_fn
    ):
        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        host_cidr = _host_cidr(0, 0)
        canonical_name = _leaf_name(0)
        alias_name = _alias_name(0)

        def attach_meta(node, obj):
            node["ip_ref"] = {
                "str": host_cidr,
                "url": f"/ipam/ip-addresses/{obj.pk}/",
                "type": "IP Address",
            }
            node["prefix_display_cidr"] = host_cidr
            return node

        attach_fn.side_effect = attach_meta
        ip_ref_fn.return_value = {
            "str": host_cidr,
            "url": "/ipam/ip-addresses/1/",
            "type": "IP Address",
        }

        def make_addr(pk, name, *, direct=False):
            obj = MagicMock()
            obj.pk = pk
            obj.name = name
            obj.comments = _alias_comments(canonical_name, host_cidr) if name != canonical_name else ""
            obj.get_absolute_url.return_value = f"/a/{pk}/"
            obj.address_type = None
            return obj

        canonical = make_addr(1, canonical_name, direct=True)
        alias = make_addr(2, alias_name)
        raw = [
            {"ct": "10", "pk": "1", "name": canonical_name},
            {"ct": "10", "pk": "2", "name": alias_name},
        ]
        nodes = _build_ipa_cell_object_tree(
            raw, {(10, 1): canonical, (10, 2): alias}
        )

        self.assertEqual(len(nodes), 1)
        self.assertTrue(nodes[0].get("cell_addresses_multi"))
        self.assertTrue(nodes[0].get("cell_addresses_compact"))
        names = [a["name"] for a in nodes[0].get("cell_addresses") or []]
        self.assertEqual(
            [a["name"] for a in nodes[0].get("cell_addresses") or []],
            [canonical_name, alias_name],
        )
        self.assertEqual(_count_ipa_object_tree_duplicates(nodes), 1)

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ip_meta")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members", return_value=[])
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref")
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_dup_name_peer_same_ipam_merged_as_cell_addresses_multi(
        self, content_type_cls, ip_ref_fn, _members_fn, attach_fn
    ):
        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        leaf_idx = 0
        host_cidr = _host_cidr(0, leaf_idx)
        canonical_name = _leaf_name(leaf_idx)
        dup_name = _dup_name(leaf_idx)
        comments = _alias_comments(canonical_name, host_cidr)

        def attach_meta(node, obj):
            node["ip_ref"] = {
                "str": host_cidr,
                "url": f"/ipam/ip-addresses/99/",
                "type": "IP Address",
            }
            node["prefix_display_cidr"] = host_cidr
            return node

        attach_fn.side_effect = attach_meta
        ip_ref_fn.return_value = {
            "str": host_cidr,
            "url": "/ipam/ip-addresses/99/",
            "type": "IP Address",
        }

        def make_addr(pk, name):
            obj = MagicMock()
            obj.pk = pk
            obj.name = name
            obj.comments = comments
            obj.get_absolute_url.return_value = f"/a/{pk}/"
            obj.address_type = None
            return obj

        canonical = make_addr(1, canonical_name)
        dup = make_addr(2, dup_name)
        raw = [
            {"ct": "10", "pk": "1", "name": canonical_name},
            {"ct": "10", "pk": "2", "name": dup_name},
        ]
        nodes = _build_ipa_cell_object_tree(raw, {(10, 1): canonical, (10, 2): dup})

        self.assertEqual(len(nodes), 1)
        self.assertTrue(nodes[0].get("cell_addresses_multi"))
        self.assertTrue(nodes[0].get("cell_addresses_compact"))
        self.assertEqual(
            [a["name"] for a in nodes[0].get("cell_addresses") or []],
            [canonical_name, dup_name],
        )
        self.assertEqual(_count_ipa_object_tree_duplicates(nodes), 1)

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ipam_stats")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ip_meta")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members", return_value=[])
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref")
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_bench_prefix_containment_nests_host_under_wider_prefixes(
        self, content_type_cls, ip_ref_fn, _members_fn, attach_fn, _stats_fn
    ):
        from ipam.models import Prefix

        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        host_cidr = _host_cidr(0, 0)
        net24 = _subnet_prefix_cidr(0)
        net20 = _wider_prefix_cidr(0, PREFIX_LEN_WIDE)
        net16 = _wider_prefix_cidr(0, PREFIX_LEN_SUPER)

        refs = {
            1: {"str": host_cidr, "url": "/ipam/ip-addresses/1/", "type": "IP Address"},
            2: {"str": net24, "url": "/ipam/prefixes/2/", "type": "Prefix"},
            3: {"str": net20, "url": "/ipam/prefixes/3/", "type": "Prefix"},
            4: {"str": net16, "url": "/ipam/prefixes/4/", "type": "Prefix"},
        }

        def attach_meta(node, obj):
            ip_ref = refs[obj.pk]
            node["ip_ref"] = {"str": ip_ref["str"], "url": ip_ref["url"]}
            node["prefix_display_cidr"] = ip_ref["str"]
            node["kind"] = "leaf" if not node.get("children") else "group"
            return node

        attach_fn.side_effect = attach_meta
        ip_ref_fn.side_effect = lambda obj: refs[obj.pk]

        def make_prefix(pk, cidr, parents=None):
            names = {2: "bench-net-00000", 3: _wide_name(0), 4: _super_name(0)}
            obj = MagicMock(spec=Prefix)
            obj.pk = pk
            obj.name = names[pk]
            obj.prefix = ipaddress.ip_network(cidr)
            obj.get_absolute_url.return_value = f"/ipam/prefixes/{pk}/"
            obj.get_parents.return_value = parents or []
            obj.address_type = None
            return obj

        def make_host(pk, name):
            obj = MagicMock()
            obj.pk = pk
            obj.name = name
            obj.get_absolute_url.return_value = f"/a/{pk}/"
            obj.address_type = None
            return obj

        slash16 = make_prefix(4, net16)
        slash20 = make_prefix(3, net20, parents=[slash16])
        slash24 = make_prefix(2, net24, parents=[slash20, slash16])
        host = make_host(1, _leaf_name(0))

        obj_by_key = {
            (10, 1): host,
            (10, 2): slash24,
            (10, 3): slash20,
            (10, 4): slash16,
        }
        raw = [
            {"ct": "10", "pk": str(pk), "name": obj_by_key[(10, pk)].name}
            for pk in (4, 3, 2, 1)
        ]
        nodes = _build_ipa_cell_object_tree(raw, obj_by_key)

        contained = _collect_flagged(nodes, "subnet_contained_in")
        self.assertGreaterEqual(len(contained), 3)
        contained_nets = {n.get("subnet_contained_in") for n in contained}
        self.assertIn(net16, contained_nets)
        dup_count = _count_ipa_object_tree_duplicates(nodes)
        self.assertGreaterEqual(dup_count, 3)

    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._build_ipa_cell_flat_address_node")
    def test_overlap_group_shared_host_gets_cell_groups_multi(
        self, build_node_fn, members_fn, content_type_cls
    ):
        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        host = MagicMock()
        host.pk = 1
        host.name = _leaf_name(0)
        host.get_absolute_url.return_value = "/a/1/"
        host.address_type = None

        subnet_grp = MagicMock()
        subnet_grp.pk = 10
        subnet_grp.name = "bench-grp-00000"
        subnet_grp.get_absolute_url.return_value = "/g/10/"
        subnet_grp.address_type = "address-group"

        ovlp_grp = MagicMock()
        ovlp_grp.pk = 11
        ovlp_grp.name = "bench-grp-ovlp-00000"
        ovlp_grp.get_absolute_url.return_value = "/g/11/"
        ovlp_grp.address_type = "address-group"

        members_fn.side_effect = lambda obj: (
            [host] if obj in (subnet_grp, ovlp_grp) else []
        )
        build_node_fn.side_effect = lambda obj, **kwargs: {
            "name": obj.name,
            "url": "#",
            "ct": str(kwargs.get("ct_id") or 10),
            "pk": str(obj.pk),
            "kind": "leaf",
            "prefix_display_cidr": _host_cidr(0, 0),
            "children": [],
        }

        raw = [
            {"ct": "10", "pk": "10", "name": subnet_grp.name},
            {"ct": "10", "pk": "11", "name": ovlp_grp.name},
        ]
        nodes = _build_ipa_cell_object_tree(
            raw, {(10, 1): host, (10, 10): subnet_grp, (10, 11): ovlp_grp}
        )

        self.assertEqual(len(nodes), 1)
        self.assertTrue(nodes[0].get("cell_groups_multi"))
        group_names = [g["name"] for g in nodes[0].get("cell_groups") or []]
        self.assertEqual(
            group_names,
            ["bench-grp-00000", "bench-grp-ovlp-00000"],
        )
        self.assertEqual(_count_ipa_object_tree_group_duplicates(nodes), 1)

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ipam_stats")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ip_meta")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref")
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_bench_rule_00011_overlap_group_members_get_subnet_containment(
        self, content_type_cls, ip_ref_fn, members_fn, attach_fn, _stats_fn
    ):
        """bench-rule-00011 style cell: overlap group + member /24 + host."""
        from ipam.models import Prefix

        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        host_cidr = _host_cidr(0, 0)
        net24 = _subnet_prefix_cidr(0)
        net24b = _subnet_prefix_cidr(1)

        refs = {
            1: {"str": host_cidr, "url": "/ipam/ip-addresses/1/", "type": "IP Address"},
            2: {"str": net24, "url": "/ipam/prefixes/2/", "type": "Prefix"},
            3: {"str": net24b, "url": "/ipam/prefixes/3/", "type": "Prefix"},
        }

        def attach_meta(node, obj):
            ip_ref = refs[obj.pk]
            node["ip_ref"] = {"str": ip_ref["str"], "url": ip_ref["url"]}
            node["prefix_display_cidr"] = ip_ref["str"]
            node["kind"] = "leaf" if obj.pk == 1 else "group"
            return node

        attach_fn.side_effect = attach_meta
        ip_ref_fn.side_effect = lambda obj: refs[obj.pk]

        def make_prefix(pk, cidr):
            obj = MagicMock(spec=Prefix)
            obj.pk = pk
            obj.name = f"bench-net-{pk:05d}"
            obj.prefix = ipaddress.ip_network(cidr)
            obj.get_absolute_url.return_value = f"/ipam/prefixes/{pk}/"
            obj.get_parents.return_value = []
            obj.address_type = None
            return obj

        def make_host(pk, name):
            obj = MagicMock()
            obj.pk = pk
            obj.name = name
            obj.get_absolute_url.return_value = f"/a/{pk}/"
            obj.address_type = None
            return obj

        host = make_host(1, _leaf_name(0))
        slash24a = make_prefix(2, net24)
        slash24b = make_prefix(3, net24b)

        ovlp_grp = MagicMock()
        ovlp_grp.pk = 11
        ovlp_grp.name = "bench-grp-ovlp-00000"
        ovlp_grp.get_absolute_url.return_value = "/g/11/"
        ovlp_grp.address_type = "address-group"

        members_fn.side_effect = lambda obj: (
            [slash24a, slash24b, host]
            if obj is ovlp_grp
            else []
        )

        obj_by_key = {
            (10, 1): host,
            (10, 2): slash24a,
            (10, 3): slash24b,
            (10, 11): ovlp_grp,
        }
        raw = [
            {"ct": "10", "pk": "11", "name": ovlp_grp.name},
            {"ct": "10", "pk": "2", "name": slash24a.name},
            {"ct": "10", "pk": "3", "name": slash24b.name},
            {"ct": "10", "pk": "1", "name": host.name},
        ]
        nodes = _build_ipa_cell_object_tree(raw, obj_by_key)

        contained = _collect_flagged(nodes, "subnet_contained_in")
        self.assertGreaterEqual(len(contained), 1)
        host_nodes = [
            n
            for n in _walk_nodes(nodes)
            if (n.get("prefix_display_cidr") or "") == host_cidr
        ]
        self.assertEqual(len(host_nodes), 1)
        self.assertEqual(host_nodes[0].get("subnet_contained_in"), net24)

    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._build_addr_tree_nodes")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._object_supports_addr_analyzer", return_value=True)
    def test_addr_tree_marks_contained_bench_prefix_as_duplicate(
        self, _supports, build_nodes_fn
    ):
        net24 = _subnet_prefix_cidr(0)
        net20 = _wider_prefix_cidr(0, PREFIX_LEN_WIDE)
        nodes = [
            {
                "kind": "group",
                "name": "bench-net-00000",
                "url": "/a/24/",
                "ip_ref": {"str": net24, "url": "/ipam/prefixes/2/", "type": "Prefix"},
                "children": [],
            },
            {
                "kind": "group",
                "name": _wide_name(0),
                "url": "/a/20/",
                "ip_ref": {"str": net20, "url": "/ipam/prefixes/3/", "type": "Prefix"},
                "children": [],
            },
        ]
        def _build_with_dup_flags(objs):
            _mark_contained_addr_duplicate_flags(nodes)
            return nodes, []

        build_nodes_fn.side_effect = _build_with_dup_flags
        analysis = _build_multi_object_addr_analyzer([MagicMock(), MagicMock()])
        flagged = analysis[0]["types"][0]["nodes"][0]
        self.assertTrue(flagged.get("count_duplicate"))
        self.assertEqual(_count_addr_tree_duplicates(analysis[0]["types"][0]["nodes"]), 1)

    def test_mark_contained_addr_duplicate_flags_bench_hierarchy(self):
        net24 = _subnet_prefix_cidr(0)
        net20 = _wider_prefix_cidr(0, PREFIX_LEN_WIDE)
        net16 = _wider_prefix_cidr(0, PREFIX_LEN_SUPER)
        nodes = [
            {
                "kind": "group",
                "name": "bench-net-00000",
                "ip_ref": {"str": net24, "type": "Prefix"},
                "children": [],
            },
            {
                "kind": "group",
                "name": _wide_name(0),
                "ip_ref": {"str": net20, "type": "Prefix"},
                "children": [],
            },
            {
                "kind": "group",
                "name": _super_name(0),
                "ip_ref": {"str": net16, "type": "Prefix"},
                "children": [],
            },
        ]
        _mark_contained_addr_duplicate_flags(nodes)
        dup_nodes = _collect_flagged(nodes, "count_duplicate")
        self.assertEqual(len(dup_nodes), 2)
        dup_names = {n["name"] for n in dup_nodes}
        self.assertEqual(dup_names, {"bench-net-00000", _wide_name(0)})


def _walk_ipa_tree_nodes(nodes):
    for node in nodes or []:
        yield node
        yield from _walk_ipa_tree_nodes(node.get("children") or [])


def _collect_tree_cidr_keys(nodes):
    keys = []
    for node in _walk_ipa_tree_nodes(nodes):
        cidr = (
            node.get("prefix_display_cidr")
            or (node.get("ip_ref") or {}).get("str")
            or ""
        ).strip()
        if cidr:
            keys.append(cidr.lower())
    return keys


class BenchRule00001CellTreeIntegrationTests(TestCase):
    """Live bench DB: bench-rule-00001 source_addresses cell tree sanity."""

    def test_bench_rule_00001_source_tree_no_duplicate_cidrs_reasonable_size(self):
        try:
            from django.contrib.contenttypes.models import ContentType

            from netbox_nsm.analyzers.ip_analyzer.ip_analyzer_service import (
                execute_ip_analyzer_merge,
                parse_object_refs,
            )
            from netbox_nsm.tests.nsm_prerequisites import (
                get_cot_field_through_model,
                get_cot_model,
                resolve_rulebook_address_field_names,
            )
        except ImportError:
            self.skipTest("NetBox environment not available")

        try:
            RuleModel, cot = get_cot_model("nsm_rb_demo_zone_addresses")
        except RuntimeError:
            self.skipTest("Bench rulebook not deployed")

        rule = RuleModel.objects.filter(name="bench-rule-00001").first()
        if rule is None:
            self.skipTest("bench-rule-00001 not loaded")

        src_field, _ = resolve_rulebook_address_field_names(cot)
        Through = get_cot_field_through_model(cot, src_field)
        refs = []
        for row in Through.objects.filter(source_id=rule.pk).order_by("id"):
            ct = ContentType.objects.get(pk=row.content_type_id)
            obj = ct.model_class().objects.filter(pk=row.object_id).first()
            if not obj:
                continue
            refs.append(
                {
                    "ct": str(row.content_type_id),
                    "pk": str(row.object_id),
                    "name": str(getattr(obj, "name", obj)),
                }
            )

        selections, objs, unsupported, raw_selections, obj_by_key = parse_object_refs(
            refs
        )
        self.assertTrue(objs)
        tree = _build_ipa_cell_object_tree(raw_selections, obj_by_key)
        all_nodes = list(_walk_ipa_tree_nodes(tree))
        cidr_keys = _collect_tree_cidr_keys(tree)
        dup_cidrs = [k for k, count in Counter(cidr_keys).items() if count > 1]

        self.assertEqual(dup_cidrs, [], msg=f"duplicate CIDR keys: {dup_cidrs[:10]}")
        self.assertLessEqual(
            len(all_nodes),
            80,
            msg=f"cell tree too large ({len(all_nodes)} nodes) — group member explosion?",
        )
        self.assertLessEqual(len(tree), 20, msg=f"too many roots ({len(tree)})")

        collapsed_wrappers = [
            node
            for node in _walk_ipa_tree_nodes(tree)
            if node.get("ipa_tree_node_type") == "collapsed_root_groups"
        ]
        self.assertEqual(
            collapsed_wrappers,
            [],
            msg="collapsed address groups must nest in the IPAM tree, not a root wrapper",
        )

        payload = execute_ip_analyzer_merge(
            selections=selections,
            objs=objs,
            unsupported=unsupported,
            raw_selections=raw_selections,
            obj_by_key=obj_by_key,
            include_html=False,
            include_structured_data=True,
        )
        self.assertLess(
            payload["count_ips"],
            20,
            msg="summary IP count must not reflect full /16 IPAM inventory",
        )
        self.assertGreaterEqual(
            payload["count_subnets"],
            18,
            msg="summary subnets must include visible prefix/group CIDR rows",
        )
        self.assertLess(
            payload["count_subnets"],
            80,
            msg="summary subnet count must not reflect full /16 IPAM inventory",
        )

        def _find(nodes, name):
            for node in nodes:
                if node.get("name") == name:
                    return node
                found = _find(node.get("children") or [], name)
                if found:
                    return found
            return None

        net24 = _find(tree, "bench-net-00000")
        self.assertIsNotNone(net24)
        self.assertNotIn(
            "addr_drilldown_lazy",
            net24,
            msg="prefix with cell children must not auto-load full IPAM drilldown",
        )
        child_kinds = [
            c.get("ipa_tree_node_type") or c.get("kind")
            for c in net24.get("children") or []
        ]
        self.assertNotIn(IPA_TREE_NODE_INFO_GAP, child_kinds)
        super_node = _find(tree, "bench-net-super-00000")
        if super_node and super_node.get("ipam_stats_short"):
            self.assertNotIn("25600", super_node["ipam_stats_short"])
