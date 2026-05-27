"""
Built-in Custom Type definitions for netbox-nsm.

These types are NOT automatically created in the database.
An administrator can install selected types via the
"Install Defaults" UI at /plugins/netbox-nsm/object/custom/types/install-builtins/.

Once installed, a type is a regular SecurityObjectType record and can be freely
edited or deleted — there is no ongoing link back to this file.
"""

BUILTIN_CUSTOM_TYPES = [
    # ── Action ────────────────────────────────────────────────────────────────
    {
        "name": "Action",
        "area": "action",
        "description": "",
        "display_template": "{name}",
        "field_definitions": [],
        "default_objects": [
            {"name": "Permit", "field_data": {}},
            {"name": "Deny",   "field_data": {}},
            {"name": "Reject", "field_data": {}},
        ],
    },
    {
        "name": "Log",
        "area": "action",
        "description": "",
        "display_template": "Log:{enabled}",
        "field_definitions": [
            {"name": "enabled", "type": "choice", "label": "Enabled", "choices": ["on", "off"]},
        ],
        "default_objects": [
            {"name": "Log-ON",  "field_data": {"enabled": "on"}},
            {"name": "Log-Off", "field_data": {"enabled": "off"}},
        ],
    },
    # ── Info ──────────────────────────────────────────────────────────────────
    {
        "name": "Comment",
        "area": "info",
        "description": "",
        "display_template": "{betreff}",
        "field_definitions": [
            {"name": "betreff", "type": "text",     "label": "Subject"},
            {"name": "notes",   "type": "markdown", "label": "Notes"},
        ],
        "default_objects": [],
    },
    {
        "name": "InstalledOn",
        "area": "info",
        "description": "",
        "display_template": "{device}",
        "field_definitions": [
            {"name": "device", "type": "object_ref", "label": "Device", "model": "dcim.Device"},
        ],
        "default_objects": [],
    },
    {
        "name": "InstallDate",
        "area": "info",
        "description": "",
        "display_template": "{date}",
        "field_definitions": [
            {"name": "date",    "type": "date",     "label": "Date"},
            {"name": "comment", "type": "markdown", "label": "Comment"},
        ],
        "default_objects": [],
    },
    # ── Services ──────────────────────────────────────────────────────────────
    {
        "name": "Applications",
        "area": "services",
        "description": "",
        "display_template": "{app_id} ({protocol})",
        "field_definitions": [
            {"name": "app_id",   "type": "text", "label": "Application ID", "required": True},
            {"name": "protocol", "type": "text", "label": "Protocol"},
            {"name": "risk",     "type": "text", "label": "Risk Level"},
        ],
        "default_objects": [],
    },
    {
        "name": "Services",
        "area": "services",
        "description": "",
        "display_template": "{name} ({protocol}/{destination_ports})",
        "field_definitions": [
            {
                "name": "protocol",
                "type": "choice",
                "label": "Protocol",
                "choices": [
                    "tcp",
                    "udp",
                    "icmp",
                    "icmpv6",
                    "sctp",
                    "gre",
                    "esp",
                    "ah",
                    "ipip",
                ],
                "required": True,
            },
            {"name": "destination_ports", "type": "text", "label": "Destination Ports"},
            {"name": "source_ports",      "type": "text", "label": "Source Ports"},
        ],
        "default_objects": [
            {"name": "HTTPS", "field_data": {"protocol": "tcp", "destination_ports": "443"}},
            {"name": "HTTP",  "field_data": {"protocol": "tcp", "destination_ports": "80"}},
            {"name": "DNS",   "field_data": {"protocol": "udp", "destination_ports": "53"}},
            {"name": "SSH",   "field_data": {"protocol": "tcp", "destination_ports": "22"}},
            {"name": "SNMP",  "field_data": {"protocol": "udp", "destination_ports": "161"}},
        ],
    },
    # ── Source / Destination ──────────────────────────────────────────────────
    {
        "name": "Addresses",
        "area": "srcdst",
        "description": "",
        "display_template": "{dns_name}",
        "field_definitions": [
            {"name": "ipam_prefix",    "type": "object_ref", "label": "Prefix",     "model": "ipam.Prefix",    "selector": True, "tab_group": "Address Parameters"},
            {"name": "ipam_ipaddress", "type": "object_ref", "label": "IP Address", "model": "ipam.IPAddress", "selector": True, "tab_group": "Address Parameters"},
            {"name": "ipam_iprange",   "type": "object_ref", "label": "IP Range",   "model": "ipam.IPRange",   "selector": True, "tab_group": "Address Parameters"},
            {"name": "dns_name",       "type": "text",       "label": "DNS Name",                               "tab_group": "Address Parameters"},
        ],
        "default_objects": [],
    },
    {
        "name": "Interface",
        "area": "srcdst",
        "description": "",
        "display_template": "{direction} {interface}",
        "field_definitions": [
            {"name": "direction", "type": "text",       "label": "Direction"},
            {"name": "device",    "type": "object_ref", "label": "Device",    "model": "dcim.Device",    "selector": True, "tab_group": "Assignment"},
            {"name": "interface", "type": "object_ref", "label": "Interface", "model": "dcim.Interface", "selector": True, "tab_group": "Assignment"},
        ],
        "default_objects": [],
    },
    {
        "name": "Labels",
        "area": "srcdst",
        "description": "",
        "display_template": "{label_type_initial}:{name}",
        "field_definitions": [
            {"__meta__": True, "hide_table_data": True},
            {
                "name": "label_type",
                "type": "choice",
                "label": "Label Type",
                "choices": ["Role", "Application", "Environment", "Location", "Flexible labels"],
                "required": True,
            },
            {
                "name": "flexible_text",
                "type": "text",
                "label": "Label Text",
                "visible_when": {"field": "label_type", "value": "Flexible labels"},
            },
            {"name": "color", "type": "text", "label": "Color"},
        ],
        "default_objects": [
            {"name": "dev", "field_data": {"label_type": "Environment"}},
            {"name": "test", "field_data": {"label_type": "Environment"}},
            {"name": "prod", "field_data": {"label_type": "Environment"}},
        ],
    },
    {
        "name": "NAT",
        "area": "srcdst",
        "description": "",
        "display_template": "{nat_type}: {source_prefix}{source_address} -> {destination_prefix}{destination_address}",
        "field_definitions": [
            {"name": "nat_type",            "type": "choice",     "label": "NAT Type", "choices": ["snat", "dnat", "masquerade", "nat64"]},
            {"name": "source_address",      "type": "object_ref", "label": "Source Address",      "model": "ipam.IPAddress", "selector": True, "tab_group": "Source"},
            {"name": "source_prefix",       "type": "object_ref", "label": "Source Prefix",       "model": "ipam.Prefix",    "selector": True, "tab_group": "Source"},
            {"name": "destination_address", "type": "object_ref", "label": "Destination Address", "model": "ipam.IPAddress", "selector": True, "tab_group": "Destination"},
            {"name": "destination_prefix",  "type": "object_ref", "label": "Destination Prefix",  "model": "ipam.Prefix",    "selector": True, "tab_group": "Destination"},
        ],
        "default_objects": [],
    },
    {
        "name": "SGTs",
        "area": "srcdst",
        "description": "",
        "display_template": "SGT-{tag_id}",
        "field_definitions": [
            {"name": "tag_id", "type": "number", "label": "SGT-ID"},
            {"name": "color",  "type": "text", "label": "Color"},
        ],
        "default_objects": [],
    },
    {
        "name": "Users",
        "area": "srcdst",
        "description": "",
        "display_template": "{user_type}: {dn}",
        "field_definitions": [
            {"name": "user_type", "type": "choice", "label": "User Type", "choices": ["local", "ldap", "radius", "saml"]},
            {"name": "dn",        "type": "text", "label": "DN / Username"},
        ],
        "default_objects": [],
    },
    {
        "name": "Zones",
        "area": "srcdst",
        "description": "",
        "display_template": "{name}",
        "field_definitions": [
            {"name": "color",       "type": "text", "label": "Color"},
            {"name": "description", "type": "text", "label": "Description"},
        ],
        "default_objects": [],
    },
]
