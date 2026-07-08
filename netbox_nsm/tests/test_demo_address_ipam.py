"""Tests for demo bundle IPAM seeding (incl. 4-level IPA hierarchy)."""

from django.test import TestCase
from ipam.models import Prefix

from netbox_nsm.bundles.demo_address_ipam import (
    DEMO_IPA_HIERARCHY,
    DEMO_IPA_HIERARCHY_ADDR_NAMES,
    seed_demo_ipa_hierarchy_ipam,
)


class DemoIpaHierarchyIpamTests(TestCase):
    def test_hierarchy_has_four_levels(self):
        self.assertEqual(len(DEMO_IPA_HIERARCHY), 4)
        kinds = [level.kind for level in DEMO_IPA_HIERARCHY]
        self.assertEqual(kinds, ["prefix", "prefix", "prefix", "host"])

    def test_hierarchy_cidrs_are_nested(self):
        cidrs = [level.cidr for level in DEMO_IPA_HIERARCHY]
        self.assertEqual(
            cidrs,
            [
                "10.210.0.0/16",
                "10.210.1.0/24",
                "10.210.1.64/26",
                "10.210.1.70/32",
            ],
        )

    def test_seed_demo_ipa_hierarchy_ipam_without_cot(self):
        self.assertEqual(seed_demo_ipa_hierarchy_ipam(), 0)

    def test_hierarchy_addr_names_match_bundle_objects(self):
        self.assertEqual(
            DEMO_IPA_HIERARCHY_ADDR_NAMES,
            frozenset(
                {
                    "demo-ipa-continent",
                    "demo-ipa-country",
                    "demo-ipa-city",
                    "demo-ipa-host",
                }
            ),
        )

    def test_seed_demo_ipa_hierarchy_ipam_creates_nested_prefixes(self):
        from netbox_custom_objects.models import CustomObjectType

        cot = CustomObjectType.objects.filter(slug="nsm_address").first()
        if cot is None:
            self.skipTest("nsm_address COT not deployed")

        model = cot.get_model()
        for level in DEMO_IPA_HIERARCHY:
            model.objects.get_or_create(name=level.addr_name, defaults={"status": "active"})

        linked = seed_demo_ipa_hierarchy_ipam()
        self.assertEqual(linked, 4)

        self.assertTrue(Prefix.objects.filter(prefix="10.210.0.0/16").exists())
        self.assertTrue(Prefix.objects.filter(prefix="10.210.1.0/24").exists())
        self.assertTrue(Prefix.objects.filter(prefix="10.210.1.64/26").exists())
