"""Interface parent host links for Security Panel and Rules."""

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from netbox_nsm.core.interface_parent import (
    get_interface_parent_host,
    interface_parent_host_payload,
)
from netbox_nsm.rulebooks.cell_html import render_rules_object_cell_html


class _Host:
    def __init__(self, pk, name, url, label_lower):
        self.pk = pk
        self._name = name
        self._url = url
        self._meta = type("Meta", (), {"label_lower": label_lower})()

    def get_absolute_url(self):
        return self._url

    def __str__(self):
        return self._name


class _Iface:
    def __init__(self, pk, label_lower, parent_attr, parent):
        self.pk = pk
        self._meta = type("Meta", (), {"label_lower": label_lower})()
        setattr(self, parent_attr, parent)

    def __str__(self):
        return "iface"


class InterfaceParentHostTests(SimpleTestCase):
    def test_dcim_interface_returns_device_parent_payload(self):
        device = _Host(7, "app-01", "/dcim/devices/7/", "dcim.device")
        iface = _Iface(170, "dcim.interface", "device", device)

        self.assertIs(get_interface_parent_host(iface), device)
        self.assertEqual(
            interface_parent_host_payload(iface),
            {"parent_url": "/dcim/devices/7/", "parent_name": "app-01"},
        )

    def test_vm_interface_returns_vm_parent_payload(self):
        vm = _Host(3, "vm-01", "/virtualization/virtual-machines/3/", "virtualization.virtualmachine")
        iface = _Iface(12, "virtualization.vminterface", "virtual_machine", vm)

        self.assertIs(get_interface_parent_host(iface), vm)
        self.assertEqual(
            interface_parent_host_payload(iface)["parent_url"],
            "/virtualization/virtual-machines/3/",
        )

    def test_rules_cell_shows_parent_before_interface(self):
        items = [
            {
                "url": "/dcim/interfaces/170/",
                "name": "GigabitEthernet1/0/1",
                "parent_url": "/dcim/devices/7/",
                "parent_name": "app-01",
                "ct": 1,
                "pk": 170,
            }
        ]
        html = render_rules_object_cell_html(items, cell_mode="stack")
        self.assertIn("app-01", html)
        self.assertIn("/dcim/devices/7/", html)
        self.assertIn("GigabitEthernet1/0/1", html)

    def test_security_panel_renders_parent_host_link(self):
        html = render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_unique_rules_total": 0,
                "nsm_rulebook_groups": [],
                "nsm_link_type_groups": [
                    {
                        "type_key": "dcim__interface",
                        "type_label": "Interfaces",
                        "count": 1,
                        "show_comment": False,
                        "show_actions": False,
                        "objects": [
                            {
                                "url": "/dcim/interfaces/170/",
                                "name": "GigabitEthernet1/0/1",
                                "parent_url": "/dcim/devices/7/",
                                "parent_name": "app-01",
                            }
                        ],
                    }
                ],
                "nsm_enforcement_point": None,
            },
        )
        self.assertIn("/dcim/devices/7/", html)
        self.assertIn("app-01", html)
        self.assertIn("GigabitEthernet1/0/1", html)

    def test_analysis_section_renders_parent_host_before_interface(self):
        html = render_to_string(
            "netbox_nsm/inc/security_links.html",
            {
                "nsm_unique_rules_total": 0,
                "nsm_rulebook_groups": [],
                "nsm_link_type_groups": [],
                "nsm_enforcement_point": None,
                "nsm_interface_analysis": [
                    {
                        "pk": 170,
                        "name": "GigabitEthernet1/0/1",
                        "url": "/dcim/interfaces/170/",
                        "parent_url": "/dcim/devices/14/",
                        "parent_name": "dmi01-akron-sw01",
                        "entry_count": 1,
                        "link_rows": [],
                        "rulebook_groups": [],
                        "api_url": "/api/rules/?ct_id=1&obj_id=170",
                    }
                ],
            },
        )
        self.assertIn("nsm-cat-analysis", html)
        self.assertIn("dmi01-akron-sw01", html)
        self.assertIn("/dcim/devices/14/", html)
        self.assertIn("GigabitEthernet1/0/1", html)
