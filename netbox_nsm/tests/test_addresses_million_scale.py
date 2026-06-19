"""Helpers for bench million-address scale script (not Setup)."""

from django.test import SimpleTestCase

from netbox_nsm.demos.addresses_million_scale import (
    ADDR_PICK_MAX,
    ADDR_PICK_MIN,
    ALIAS_STRIDE,
    BENCH_OVERLAP_SHOWCASE_RULE_COUNT,
    BENCH_ZONE_COUNT,
    DEFAULT_LEAF_COUNT,
    DEFAULT_RULE_COUNT,
    GROUP_PICK_MAX,
    GROUP_PICK_MIN,
    HOSTS_PER_SUBNET,
    OVERLAP_ALIAS_STRIDE,
    OVERLAP_BUCKET_PICK_PROBABILITY,
    OVERLAP_BUCKET_RATIO,
    OVERLAP_DEMO_LEAF_IDX,
    OVERLAP_DEMO_RULE_COUNT,
    OVERLAP_DUP_NAME_STRIDE,
    OVERLAP_LEAVES_PER_GROUP,
    PREFIX_LEN_SUPER,
    PREFIX_LEN_WIDE,
    SCALE_DEMO_50K_LEAF_COUNT,
    SCALE_DEMO_50K_RULE_COUNT,
    SHOWCASE_ADDR_PICK_MAX,
    SHOWCASE_ADDR_PICK_MIN,
    SHOWCASE_GROUP_PICK_MAX,
    SHOWCASE_GROUP_PICK_MIN,
    SUBNET_COUNT,
    SUBNETS_PER_SUPER,
    SUBNETS_PER_WIDE,
    _alias_comments,
    _alias_name,
    _alias_stride_for_leaf,
    _bench_host_name,
    _bench_iface_name,
    _bench_zone_name,
    _build_bench_address_lookups,
    _dup_name,
    _group_name,
    _grp_ovlp_name,
    _host_cidr,
    _leaf_indices,
    _leaf_in_overlap_bucket,
    _leaf_name,
    _overlap_demo_cell_selection,
    _overlap_bucket_leaf_count,
    _overlap_bucket_subnet_count,
    _pick_counts,
    _pick_regular_addresses,
    _showcase_bench_leaf_indices,
    _showcase_cell_counts,
    _showcase_host_leaf,
    _showcase_leaf_for_side_alias_dup,
    _showcase_host_leaf_for_side,
    _showcase_host_leaf_for_side,
    _showcase_leaf_for_side_alias_dup,
    _showcase_leaf_with_alias_and_dup,
    _subnet_name,
    _subnet_prefix_cidr,
    _super_name,
    _wide_name,
    _wider_prefix_cidr,
    overlap_demo_rule_descriptions,
)
from netbox_nsm.rulebooks.templates import (
    BENCH_RULEBOOK_FIELD_NAMES,
    bench_rulebook_schema_yaml,
    parse_rulebook_schema_yaml,
)


class AddressesMillionScaleHelperTests(SimpleTestCase):
    def test_subnet_cidr_range(self):
        self.assertEqual(_subnet_prefix_cidr(0), "10.128.0.0/24")
        self.assertEqual(_subnet_prefix_cidr(255), "10.128.255.0/24")
        self.assertEqual(_subnet_prefix_cidr(256), "10.129.0.0/24")

    def test_wider_prefix_cidr_blocks(self):
        self.assertEqual(_wider_prefix_cidr(0, PREFIX_LEN_WIDE), "10.128.0.0/20")
        self.assertEqual(_wider_prefix_cidr(16, PREFIX_LEN_WIDE), "10.128.16.0/20")
        self.assertEqual(_wider_prefix_cidr(0, PREFIX_LEN_SUPER), "10.128.0.0/16")
        self.assertEqual(_wider_prefix_cidr(256, PREFIX_LEN_SUPER), "10.129.0.0/16")

    def test_host_cidr_in_subnet(self):
        self.assertEqual(_host_cidr(0, 0), "10.128.0.1/32")
        self.assertEqual(_host_cidr(0, 99), "10.128.0.100/32")

    def test_leaf_index_mapping(self):
        self.assertEqual(_leaf_indices(0), (0, 0))
        self.assertEqual(_leaf_indices(99), (0, 99))
        self.assertEqual(_leaf_indices(100), (1, 0))
        self.assertEqual(
            _leaf_indices(SUBNET_COUNT * HOSTS_PER_SUBNET - 1)[0], SUBNET_COUNT - 1
        )

    def test_leaf_name_padding(self):
        self.assertEqual(_leaf_name(0), "bench-ip-0000000")
        self.assertEqual(_leaf_name(199999), "bench-ip-0199999")

    def test_bench_host_and_iface_names(self):
        self.assertEqual(_bench_host_name(0), "bench-host-0000000")
        self.assertEqual(_bench_iface_name(12), "bench-iface-0000012")

    def test_showcase_bench_leaf_indices_cover_rules_one_to_twenty(self):
        limit = _overlap_bucket_leaf_count(SCALE_DEMO_50K_LEAF_COUNT)
        indices = _showcase_bench_leaf_indices(overlap_leaf_limit=limit)
        self.assertGreater(len(indices), 0)
        for leaf_idx in indices:
            self.assertLess(leaf_idx, limit)
        for rule_index in range(1, 6):
            leaf_idx = _showcase_leaf_with_alias_and_dup(
                rule_index, overlap_leaf_limit=limit
            )
            self.assertIn(leaf_idx, indices)
        for rule_index in range(6, 11):
            leaf_idx = _showcase_host_leaf(rule_index, overlap_leaf_limit=limit)
            self.assertIn(leaf_idx, indices)
        for rule_index in range(11, 16):
            pair_idx = rule_index - 11
            for subnet_idx in (pair_idx, pair_idx + 1):
                self.assertIn(subnet_idx * HOSTS_PER_SUBNET, indices)
        for rule_index in range(16, 21):
            self.assertIn((rule_index - 16) * HOSTS_PER_SUBNET, indices)

    def test_alias_stride_and_comments(self):
        self.assertEqual(_alias_name(0), "bench-alias-0000000")
        self.assertEqual(
            _alias_comments("bench-ip-0000000", "10.128.0.1/32"),
            "bench_canonical=bench-ip-0000000; network=10.128.0.1/32",
        )
        self.assertEqual(0 % ALIAS_STRIDE, 0)
        self.assertNotEqual(1 % ALIAS_STRIDE, 0)

    def test_overlap_bucket_sizing(self):
        self.assertEqual(_overlap_bucket_leaf_count(50_000), 3_750)
        self.assertEqual(_overlap_bucket_subnet_count(50_000), 38)
        self.assertEqual(_overlap_bucket_leaf_count(1000), 75)
        self.assertEqual(_overlap_bucket_subnet_count(1000), 1)
        self.assertGreaterEqual(
            _overlap_bucket_leaf_count(DEFAULT_LEAF_COUNT) / DEFAULT_LEAF_COUNT,
            0.05,
        )
        self.assertLessEqual(
            _overlap_bucket_leaf_count(DEFAULT_LEAF_COUNT) / DEFAULT_LEAF_COUNT,
            0.10,
        )

    def test_overlap_alias_stride_in_bucket(self):
        overlap_limit = _overlap_bucket_leaf_count(50_000)
        self.assertTrue(_leaf_in_overlap_bucket(0, overlap_limit))
        self.assertFalse(_leaf_in_overlap_bucket(overlap_limit, overlap_limit))
        self.assertEqual(
            _alias_stride_for_leaf(0, overlap_limit), OVERLAP_ALIAS_STRIDE
        )
        self.assertEqual(
            _alias_stride_for_leaf(overlap_limit, overlap_limit), ALIAS_STRIDE
        )
        self.assertEqual(OVERLAP_ALIAS_STRIDE, 4)
        self.assertLess(OVERLAP_ALIAS_STRIDE, ALIAS_STRIDE)

    def test_dup_name_and_wider_naming(self):
        self.assertEqual(_dup_name(12), "bench-dup-0000012")
        self.assertEqual(_wide_name(0), "bench-net-wide-00000")
        self.assertEqual(_super_name(0), "bench-net-super-00000")
        self.assertEqual(_grp_ovlp_name(3), "bench-grp-ovlp-00003")
        self.assertEqual(OVERLAP_DUP_NAME_STRIDE, 6)
        self.assertEqual(OVERLAP_LEAVES_PER_GROUP, 5)
        self.assertEqual(SUBNETS_PER_WIDE, 16)
        self.assertEqual(SUBNETS_PER_SUPER, 256)
        self.assertEqual(OVERLAP_BUCKET_RATIO, 0.075)

    def test_group_and_zone_names(self):
        self.assertEqual(_group_name(0), "bench-grp-00000")
        self.assertEqual(_bench_zone_name(0), "bench-zone-001")
        self.assertEqual(BENCH_ZONE_COUNT, 50)

    def test_pick_counts_respects_pool_size(self):
        import random

        rng = random.Random(1)
        picked = _pick_counts(
            rng, pool_size=3, min_n=ADDR_PICK_MIN, max_n=ADDR_PICK_MAX
        )
        self.assertGreaterEqual(picked, 1)
        self.assertLessEqual(picked, 3)
        self.assertEqual(
            _pick_counts(rng, pool_size=0, min_n=GROUP_PICK_MIN, max_n=GROUP_PICK_MAX),
            0,
        )

    def test_rule_pick_limits(self):
        self.assertEqual(ADDR_PICK_MIN, 1)
        self.assertEqual(ADDR_PICK_MAX, 8)
        self.assertEqual(GROUP_PICK_MIN, 1)
        self.assertEqual(GROUP_PICK_MAX, 5)

    def test_scale_demo_50k_constants(self):
        self.assertEqual(SCALE_DEMO_50K_LEAF_COUNT, 50_000)
        self.assertEqual(
            SCALE_DEMO_50K_RULE_COUNT,
            round(DEFAULT_RULE_COUNT * 50_000 / DEFAULT_LEAF_COUNT),
        )

    def test_bench_rulebook_schema_fields(self):
        type_def = parse_rulebook_schema_yaml(bench_rulebook_schema_yaml())
        field_names = [field["name"] for field in type_def["fields"]]
        self.assertEqual(field_names, list(BENCH_RULEBOOK_FIELD_NAMES))
        self.assertIn("source_zones", field_names)
        self.assertIn("destination_addresses", field_names)

    def test_overlap_prefix_contains_host(self):
        """/24 host sits inside overlap-bucket /20 and /16 parents."""
        host = _host_cidr(0, 0)
        wide = _wider_prefix_cidr(0, PREFIX_LEN_WIDE)
        supernet = _wider_prefix_cidr(0, PREFIX_LEN_SUPER)
        self.assertTrue(host.startswith("10.128.0."))
        self.assertEqual(wide, "10.128.0.0/20")
        self.assertEqual(supernet, "10.128.0.0/16")
        self.assertEqual(_subnet_prefix_cidr(0), "10.128.0.0/24")

    def test_overlap_showcase_constants(self):
        self.assertEqual(BENCH_OVERLAP_SHOWCASE_RULE_COUNT, 20)
        self.assertEqual(OVERLAP_DEMO_RULE_COUNT, BENCH_OVERLAP_SHOWCASE_RULE_COUNT)
        self.assertGreater(OVERLAP_BUCKET_PICK_PROBABILITY, 0.5)

    def test_showcase_leaf_indices_share_alias_and_dup(self):
        limit = _overlap_bucket_leaf_count(SCALE_DEMO_50K_LEAF_COUNT)
        for rule_index in range(1, 6):
            leaf_idx = _showcase_leaf_with_alias_and_dup(
                rule_index, overlap_leaf_limit=limit
            )
            self.assertEqual(leaf_idx % OVERLAP_ALIAS_STRIDE, 0)
            self.assertEqual(leaf_idx % OVERLAP_DUP_NAME_STRIDE, 0)

    def test_showcase_cell_counts_are_one_to_ten(self):
        for rule_index in range(1, 21):
            src_n, dst_n, src_gn, dst_gn = _showcase_cell_counts(rule_index)
            for count in (src_n, dst_n):
                self.assertGreaterEqual(count, SHOWCASE_ADDR_PICK_MIN)
                self.assertLessEqual(count, SHOWCASE_ADDR_PICK_MAX)
            for count in (src_gn, dst_gn):
                self.assertGreaterEqual(count, SHOWCASE_GROUP_PICK_MIN)
                self.assertLessEqual(count, SHOWCASE_GROUP_PICK_MAX)

    def test_overlap_demo_rule_descriptions_cover_first_twenty_rules(self):
        descriptions = overlap_demo_rule_descriptions()
        self.assertEqual(len(descriptions), BENCH_OVERLAP_SHOWCASE_RULE_COUNT)
        self.assertEqual(descriptions[0]["name"], "bench-rule-00001")
        self.assertEqual(descriptions[-1]["name"], "bench-rule-00020")
        self.assertIn("bench-ip-", descriptions[0]["source_objects"])
        self.assertIn("bench-alias-", descriptions[0]["source_objects"])
        self.assertIn("bench-dup-", descriptions[0]["source_objects"])
        self.assertIn("bench-ip-", descriptions[0]["destination_objects"])
        self.assertIn("counts", descriptions[0])
        self.assertIn("bench-host-", descriptions[0]["ipam_host"])
        self.assertIn("bench-iface-", descriptions[0]["ipam_host"])
        self.assertIn("ipam_host", descriptions[15])
        self.assertEqual(descriptions[15]["source_pattern"], "subnets_with_host_all")
        self.assertIn("destination_objects", descriptions[15])

    def _make_showcase_lookups(self):
        def obj(name):
            return type("Obj", (), {"pk": hash(name), "name": name})()

        limit = 1000
        leaves = [obj(_leaf_name(i)) for i in range(limit)]
        aliases = [obj(_alias_name(i)) for i in range(0, limit, 12)]
        dup_names = [obj(_dup_name(i)) for i in range(0, limit, 12)]
        subnet_count = (limit + HOSTS_PER_SUBNET - 1) // HOSTS_PER_SUBNET
        net_addrs = [obj(_subnet_name(i)) for i in range(subnet_count)]
        wide_addrs = [obj(_wide_name(i)) for i in range((subnet_count + 15) // 16)]
        super_addrs = [obj(_super_name(0))]
        groups = [obj(_group_name(i)) for i in range(subnet_count)]
        overlap_groups = [obj(_grp_ovlp_name(i)) for i in range(max(1, subnet_count - 1))]
        return _build_bench_address_lookups(
            leaves=leaves,
            aliases=aliases,
            dup_names=dup_names,
            net_addrs=net_addrs,
            wide_addrs=wide_addrs,
            super_addrs=super_addrs,
            groups=groups,
            overlap_groups=overlap_groups,
            overlap_leaf_limit=limit,
        )

    def test_overlap_demo_cell_selection_populates_both_sides(self):
        lookups = self._make_showcase_lookups()
        for rule_index in range(1, 21):
            src, dst, src_grps, dst_grps = _overlap_demo_cell_selection(
                rule_index, lookups
            )
            self.assertGreaterEqual(len(src), 1, msg=f"rule {rule_index} src")
            self.assertGreaterEqual(len(dst), 1, msg=f"rule {rule_index} dst")
            self.assertGreaterEqual(len(src_grps), 1, msg=f"rule {rule_index} src grps")
            self.assertGreaterEqual(len(dst_grps), 1, msg=f"rule {rule_index} dst grps")
            self.assertLessEqual(len(src), SHOWCASE_ADDR_PICK_MAX)
            self.assertLessEqual(len(dst), SHOWCASE_ADDR_PICK_MAX)
            self.assertLessEqual(len(src_grps), SHOWCASE_GROUP_PICK_MAX)
            self.assertLessEqual(len(dst_grps), SHOWCASE_GROUP_PICK_MAX)

    def test_overlap_demo_cell_selection_includes_overlap_bundle(self):
        lookups = self._make_showcase_lookups()
        limit = lookups.overlap_leaf_limit
        src_leaf1 = _showcase_leaf_for_side_alias_dup(1, "src", limit)
        dst_leaf1 = _showcase_leaf_for_side_alias_dup(1, "dst", limit)
        src1, dst1, _, _ = _overlap_demo_cell_selection(1, lookups)
        src_subnet, _ = _leaf_indices(src_leaf1)
        dst_subnet, _ = _leaf_indices(dst_leaf1)
        src_names = {o.name for o in src1}
        dst_names = {o.name for o in dst1}
        self.assertIn(_leaf_name(src_leaf1), src_names)
        self.assertIn(_subnet_name(src_subnet), src_names)
        self.assertIn(_leaf_name(dst_leaf1), dst_names)
        self.assertIn(_subnet_name(dst_subnet), dst_names)

        host_leaf6 = _showcase_host_leaf_for_side(6, "src", limit)
        dst_leaf6 = _showcase_host_leaf_for_side(6, "dst", limit)
        subnet_idx6, _ = _leaf_indices(host_leaf6)
        dst_subnet6, _ = _leaf_indices(dst_leaf6)
        src6, dst6, _, _ = _overlap_demo_cell_selection(6, lookups)
        src6_names = {o.name for o in src6}
        dst6_names = {o.name for o in dst6}
        self.assertIn(_leaf_name(host_leaf6), src6_names)
        self.assertIn(_subnet_name(subnet_idx6), src6_names)
        self.assertIn(_leaf_name(dst_leaf6), dst6_names)
        self.assertIn(_subnet_name(dst_subnet6), dst6_names)

        src11, dst11, grps11, grps_dst11 = _overlap_demo_cell_selection(11, lookups)
        src11_names = {o.name for o in src11}
        self.assertIn(_subnet_name(0), src11_names)
        self.assertIn(_subnet_name(1), src11_names)
        self.assertTrue(dst11)
        src11_total = len(src11) + len(grps11)
        if src11_total >= 2:
            self.assertTrue(grps11)
        self.assertTrue(grps_dst11 or dst11)

        src16, dst16, _, _ = _overlap_demo_cell_selection(16, lookups)
        for cell in (src16, dst16):
            names = {o.name for o in cell}
            self.assertTrue(any(n.startswith("bench-net-") for n in names))
            self.assertTrue(any(n.startswith("bench-ip-") for n in names))

    def test_pick_regular_addresses_includes_prefix(self):
        import random

        def obj(name, *, is_prefix=False):
            return type(
                "Obj",
                (),
                {"pk": hash(name), "name": name, "is_prefix": is_prefix},
            )()

        prefix_pool = [
            obj("bench-net-00000", is_prefix=True),
            obj("bench-net-wide-00000", is_prefix=True),
        ]
        overlap_pool = [
            obj("bench-ip-0000000"),
            obj("bench-alias-0000000"),
        ]
        address_pool = overlap_pool + prefix_pool + [obj("bench-ip-0500000")]

        rng = random.Random(99)
        for _ in range(20):
            picked = _pick_regular_addresses(
                rng,
                address_pool=address_pool,
                prefix_pool=prefix_pool,
                overlap_pool=overlap_pool,
                count=3,
            )
            self.assertGreaterEqual(len(picked), 1)
            self.assertTrue(
                any(obj.name.startswith("bench-net") for obj in picked),
                "regular rule picks must include at least one prefix object",
            )


from django.contrib.contenttypes.models import ContentType

from ipam.models import IPAddress, Prefix
from netbox_nsm.demos.addresses_million_scale import (
    _get_or_create_prefix,
    create_addresses_million_scale,
    purge_bench_data,
)
from netbox_nsm.demos.cot_demo_common import ensure_nsm_prerequisites, get_cot_model
from netbox_nsm.objects.address_ipam_fk import iter_address_ipam_fk_refs
from utilities.testing import TestCase
from virtualization.models import VMInterface, VirtualMachine


class AddressesMillionScalePrefixTests(TestCase):
    def test_get_or_create_prefix_tolerates_duplicates(self):
        cidr = "10.198.0.0/24"
        p1 = Prefix.objects.create(prefix=cidr, status="active")
        p2 = Prefix.objects.create(prefix=cidr, status="active")
        result = _get_or_create_prefix(cidr)
        self.assertIn(result.pk, (p1.pk, p2.pk))
        self.assertEqual(str(result.prefix), cidr)


class AddressesMillionScaleShowcaseHostTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_nsm_prerequisites()

    def test_showcase_ipam_hosts_created_for_overlap_rules(self):
        summary = create_addresses_million_scale(leaf_count=1000, rule_count=0)
        expected_indices = summary["showcase_leaf_indices"]
        self.assertGreater(len(expected_indices), 0)
        self.assertEqual(summary["showcase_hosts"], len(expected_indices))
        self.assertEqual(summary["showcase_interfaces"], len(expected_indices))
        self.assertEqual(summary["showcase_ips_assigned"], len(expected_indices))

        for leaf_idx in expected_indices:
            host_name = _bench_host_name(leaf_idx)
            iface_name = _bench_iface_name(leaf_idx)
            vm = VirtualMachine.objects.get(name=host_name)
            iface = VMInterface.objects.get(virtual_machine=vm, name=iface_name)
            ip_obj = IPAddress.objects.get(address=_host_cidr(*_leaf_indices(leaf_idx)))
            self.assertEqual(ip_obj.assigned_object_id, iface.pk)
            self.assertEqual(
                ip_obj.assigned_object_type_id,
                ContentType.objects.get_for_model(VMInterface).pk,
            )
            AddrModel, _ = get_cot_model("nsm_address", "nsm_addresses")
            addr = AddrModel.objects.get(name=_leaf_name(leaf_idx))
            refs = list(iter_address_ipam_fk_refs(addr))
            self.assertEqual(len(refs), 1)
            self.assertEqual(refs[0].ipam_obj.pk, ip_obj.pk)

    def test_purge_removes_showcase_hosts(self):
        create_addresses_million_scale(leaf_count=1000, rule_count=0)
        self.assertTrue(
            VirtualMachine.objects.filter(name__startswith="bench-host-").exists()
        )
        purge_summary = purge_bench_data()
        self.assertGreater(purge_summary["vms_deleted"], 0)
        self.assertFalse(
            VirtualMachine.objects.filter(name__startswith="bench-host-").exists()
        )
