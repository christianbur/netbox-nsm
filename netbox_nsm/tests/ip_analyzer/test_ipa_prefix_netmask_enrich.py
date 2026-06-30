"""IPA object tree should attach netmask labels for inferred CIDRs."""

from django.test import SimpleTestCase

from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import _enrich_ipa_object_tree_cidr_from_names


class IpaPrefixNetmaskEnrichTests(SimpleTestCase):
    def test_enrich_attaches_netmask_for_inferred_prefix_cidr(self):
        nodes = [
            {
                "name": "dm-addr-10-112-134-0-24",
                "kind": "leaf",
                "children": [],
            }
        ]
        _enrich_ipa_object_tree_cidr_from_names(nodes)
        self.assertEqual(nodes[0]["prefix_display_cidr"], "10.112.134.0/24")
        self.assertEqual(
            nodes[0]["prefix_display_netmask"], "10.112.134.0/255.255.255.0"
        )
