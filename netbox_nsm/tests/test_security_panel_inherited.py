"""Tests for Security Panel inherited link merge helpers."""

from django.test import SimpleTestCase

from netbox_nsm.security.tab.context import finalize_link_type_groups


class SecurityPanelInheritedPayloadTests(SimpleTestCase):
    def test_finalize_marks_inherited_rows_without_actions(self):
        groups = finalize_link_type_groups(
            [
                {
                    "type_key": "netbox_custom_objects__nsmzone",
                    "type_label": "Zones",
                    "count": 1,
                    "objects": [
                        {
                            "url": "/zones/1/",
                            "name": "prod",
                            "inherited_from_url": "/ipam/prefixes/1/",
                            "inherited_from_name": "10.0.0.0/8",
                        }
                    ],
                }
            ]
        )
        self.assertFalse(groups[0]["show_actions"])

    def test_finalize_shows_actions_for_inherited_analyzable_rows(self):
        groups = finalize_link_type_groups(
            [
                {
                    "type_key": "netbox_custom_objects__nsm_addresses",
                    "type_label": "Addresses",
                    "count": 1,
                    "objects": [
                        {
                            "url": "/plugins/custom-objects/nsm_addresses/10/",
                            "name": "demo-addr-0010",
                            "addr_analyzable": True,
                            "inherited_from_url": "/ipam/prefixes/1/",
                            "inherited_from_name": "10.245.10.0/24",
                        }
                    ],
                }
            ]
        )
        self.assertTrue(groups[0]["show_actions"])
