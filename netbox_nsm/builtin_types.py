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
        "icon": "mdi-lightning-bolt",
        "description": "",
        "field_definitions": [
            {"name": "action", "type": "text", "label": "Action (permit/deny/reject)", "required": True},
        ],
    },
    {
        "name": "Filter",
        "area": "action",
        "icon": "mdi-filter-outline",
        "description": "",
        "field_definitions": [
            {"name": "family", "type": "text", "label": "Family (inet/inet6)"},
            {"name": "rules", "type": "text", "label": "Rules"},
        ],
    },
    {
        "name": "Log",
        "area": "action",
        "icon": "mdi-clipboard-text-outline",
        "description": "",
        "field_definitions": [
            {"name": "enabled", "type": "text", "label": "Enabled (yes/no)"},
        ],
    },
    {
        "name": "Policer",
        "area": "action",
        "icon": "mdi-speedometer",
        "description": "",
        "field_definitions": [
            {"name": "bandwidth_limit", "type": "text", "label": "Bandwidth Limit (kbps)"},
            {"name": "bandwidth_percent", "type": "text", "label": "Bandwidth (%)"},
        ],
    },
    # ── Info ──────────────────────────────────────────────────────────────────
    {
        "name": "Comment",
        "area": "info",
        "icon": "mdi-comment-text-outline",
        "description": "",
        "field_definitions": [
            {"name": "betreff", "type": "text", "label": "Subject"},
            {"name": "notes", "type": "markdown", "label": "Notes"},
        ],
    },
    {
        "name": "InstalledOn",
        "area": "info",
        "icon": "mdi-harddisk",
        "description": "",
        "field_definitions": [
            {"name": "device", "type": "object_ref", "label": "Device", "model": "dcim.Device"},
        ],
    },
    {
        "name": "InstallDate",
        "area": "info",
        "icon": "mdi-calendar-plus",
        "description": "",
        "field_definitions": [
            {"name": "date", "type": "date", "label": "Date"},
            {"name": "comment", "type": "markdown", "label": "Comment"},
        ],
    },
    {
        "name": "ModifiedDate",
        "area": "info",
        "icon": "mdi-calendar-edit",
        "description": "",
        "field_definitions": [
            {"name": "date", "type": "date", "label": "Date"},
            {"name": "comment", "type": "markdown", "label": "Comment"},
        ],
    },
    {
        "name": "ReviewedDate",
        "area": "info",
        "icon": "mdi-calendar-check",
        "description": "",
        "field_definitions": [
            {"name": "date", "type": "date", "label": "Date"},
            {"name": "comment", "type": "markdown", "label": "Comment"},
        ],
    },
    # ── Services ──────────────────────────────────────────────────────────────
    {
        "name": "Applications",
        "area": "services",
        "icon": "mdi-application-brackets-outline",
        "description": "",
        "field_definitions": [
            {"name": "app_id", "type": "text", "label": "App-ID"},
            {"name": "category", "type": "text", "label": "Category"},
            {"name": "subcategory", "type": "text", "label": "Subcategory"},
            {"name": "technology", "type": "text", "label": "Technology"},
            {"name": "protocol", "type": "text", "label": "Protocol"},
            {"name": "std_ports", "type": "text", "label": "Standard Ports"},
            {"name": "reference", "type": "text", "label": "Reference"},
        ],
    },
    {
        "name": "Services",
        "area": "services",
        "icon": "mdi-server-network",
        "description": "",
        "field_definitions": [
            {"name": "protocol", "type": "text", "label": "Protocol", "required": True},
            {"name": "destination_ports", "type": "text", "label": "Destination Ports"},
            {"name": "source_ports", "type": "text", "label": "Source Ports"},
        ],
    },
    # ── Source / Destination ──────────────────────────────────────────────────
    {
        "name": "Addresses",
        "area": "srcdst",
        "icon": "mdi-ip-network-outline",
        "description": "",
        "field_definitions": [
            {"name": "ipam_prefix", "type": "object_ref", "label": "Prefix", "model": "ipam.Prefix", "selector": True, "tab_group": "Address Parameters"},
            {"name": "ipam_ipaddress", "type": "object_ref", "label": "IP Address", "model": "ipam.IPAddress", "selector": True, "tab_group": "Address Parameters"},
            {"name": "ipam_iprange", "type": "object_ref", "label": "IP Range", "model": "ipam.IPRange", "selector": True, "tab_group": "Address Parameters"},
            {"name": "dns_name", "type": "text", "label": "DNS Name", "tab_group": "Address Parameters"},
        ],
    },
    {
        "name": "Interface",
        "area": "srcdst",
        "icon": "mdi-ethernet",
        "description": "",
        "field_definitions": [
            {"name": "direction", "type": "text", "label": "Direction"},
            {"name": "device", "type": "object_ref", "label": "Device", "model": "dcim.Device", "selector": True, "tab_group": "Assignment"},
            {"name": "interface", "type": "object_ref", "label": "Interface", "model": "dcim.Interface", "selector": True, "tab_group": "Assignment"},
        ],
    },
    {
        "name": "Labels",
        "area": "srcdst",
        "icon": "mdi-label-outline",
        "description": "",
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
    },
    {
        "name": "NAT",
        "area": "srcdst",
        "icon": "mdi-swap-horizontal",
        "description": "",
        "field_definitions": [
            {"name": "nat_type", "type": "text", "label": "NAT Type"},
            {"name": "source_address", "type": "object_ref", "label": "Source Address", "model": "ipam.IPAddress", "selector": True, "tab_group": "Source"},
            {"name": "source_prefix", "type": "object_ref", "label": "Source Prefix", "model": "ipam.Prefix", "selector": True, "tab_group": "Source"},
            {"name": "destination_address", "type": "object_ref", "label": "Destination Address", "model": "ipam.IPAddress", "selector": True, "tab_group": "Destination"},
            {"name": "destination_prefix", "type": "object_ref", "label": "Destination Prefix", "model": "ipam.Prefix", "selector": True, "tab_group": "Destination"},
        ],
    },
    {
        "name": "SGTs",
        "area": "srcdst",
        "icon": "mdi-shield-lock-outline",
        "description": "",
        "field_definitions": [
            {"name": "tag_id", "type": "text", "label": "SGT-ID (number)"},
            {"name": "color", "type": "text", "label": "Color"},
        ],
    },
    {
        "name": "Users",
        "area": "srcdst",
        "icon": "mdi-account-outline",
        "description": "",
        "field_definitions": [
            {"name": "user_type", "type": "text", "label": "User Type (local/ldap/radius/saml)"},
            {"name": "dn", "type": "text", "label": "DN / Username"},
        ],
    },
    {
        "name": "Zones",
        "area": "srcdst",
        "icon": "mdi-shield-outline",
        "description": "",
        "field_definitions": [
            {"name": "color", "type": "text", "label": "Color"},
            {"name": "description", "type": "text", "label": "Description"},
        ],
    },
]
