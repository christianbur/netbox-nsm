"""Built-in Custom Type definitions for netbox_nsm.

These types describe the *catalog* that the "Sync built-in types" button on
the Object-Builder page applies to ``netbox-custom-objects``. The portable
schema generator (`netbox_nsm.custom_objects_schema`) automatically injects
the following fields into every type, so they MUST NOT be repeated here:

* ``name``        — text, primary, required (id=1)
* ``description`` — text (id=3)
* ``comments``    — longtext (id=6)
* ``color``       — text (id=7)

IDs 2, 4, 5 (slug / owner_group / owner) are intentionally NOT injected.
Add them explicitly in ``field_definitions`` when needed.

Plus the dynamic-model base contributes ``id``, ``created``, ``last_updated``,
tags, bookmarks, journal entries and subscriptions for free.

Keys used by the schema builder:

* ``name``                — human-readable type name (also slugified for the COT slug)
* ``areas``               — list of section slugs (``source``+``destination``
                           are collapsed into ``srcdst``)
* ``description``         — short description (clipped to 200 chars)
* ``display_template``    — format string stored in ``NSMTypeConfig``
* ``field_definitions``   — list of fields; supported types: ``text``,
                           ``markdown``, ``number``/``integer``, ``boolean``,
                           ``date``, ``json``/``table``, ``choice`` (with
                           ``choices``), ``object_ref`` (with ``model``)
* ``default_objects``     — list of ``{"name": ..., "field_data": {...}}``

UI hints like ``selector``, ``tab_group``, ``visible_when`` and ``__meta__``
markers are intentionally NOT used here — they have no equivalent in the
portable schema and are silently ignored anyway.
"""

BUILTIN_CUSTOM_TYPES = [
    # ── Action ────────────────────────────────────────────────────────────────
    {
        "name": "Action",
        "areas": ["action"],
        "description": "Outcome a security rule takes on matched traffic.",
        "order_id": 200,
        "display_template": "{name}",
        "field_definitions": [],
        "default_objects": [
            {"name": "Permit", "field_data": {"color": "#28a745"}},
            {"name": "Deny", "field_data": {"color": "#dc3545"}},
            {"name": "Drop", "field_data": {"color": "#6c757d"}},
        ],
    },
    # ── Services ──────────────────────────────────────────────────────────────
    {
        "name": "Services",
        "areas": ["services"],
        "description": "Represents exactly one network service (protocol + optional port).",
        "order_id": 100,
        "display_template": "{name} ({protocol}/{port})",
        "field_definitions": [
            {
                "name": "protocol",
                "type": "choice",
                "label": "Protocol",
                "choices": [
                    "tcp",
                    "udp",
                    "sctp",
                    "icmp",
                    "icmpv6",
                    "gre",
                    "esp",
                    "ah",
                    "ip",
                    "any",
                ],
                "group_name": "NSM Service",
            },
            {
                "name": "port",
                "type": "integer",
                "label": "Port",
                "description": "Port 0\u201365535 (TCP/UDP/SCTP only).",
                "validation_minimum": 0,
                "validation_maximum": 65535,
                "group_name": "NSM Service",
            },
            {
                "name": "group",
                "type": "multiobject",
                "label": "Group",
                "description": "Group(s) this service belongs to.",
                "model": "custom-objects.nsm_services",
                "group_name": "NSM Service",
            },
        ],
        "default_objects": [
            # Web
            {"name": "HTTP", "field_data": {"protocol": "tcp", "port": 80}},
            {"name": "HTTPS", "field_data": {"protocol": "tcp", "port": 443}},
            {"name": "HTTP-Alt", "field_data": {"protocol": "tcp", "port": 8080}},
            {"name": "HTTPS-Alt", "field_data": {"protocol": "tcp", "port": 8443}},
            # DNS / NTP
            {"name": "DNS-UDP", "field_data": {"protocol": "udp", "port": 53}},
            {"name": "DNS-TCP", "field_data": {"protocol": "tcp", "port": 53}},
            {"name": "NTP", "field_data": {"protocol": "udp", "port": 123}},
            # Remote access
            {"name": "SSH", "field_data": {"protocol": "tcp", "port": 22}},
            {"name": "Telnet", "field_data": {"protocol": "tcp", "port": 23}},
            {"name": "RDP", "field_data": {"protocol": "tcp", "port": 3389}},
            # Mail
            {"name": "SMTP", "field_data": {"protocol": "tcp", "port": 25}},
            {"name": "SMTPS", "field_data": {"protocol": "tcp", "port": 465}},
            {"name": "SMTP-STARTTLS", "field_data": {"protocol": "tcp", "port": 587}},
            {"name": "IMAP", "field_data": {"protocol": "tcp", "port": 143}},
            {"name": "IMAPS", "field_data": {"protocol": "tcp", "port": 993}},
            {"name": "POP3", "field_data": {"protocol": "tcp", "port": 110}},
            {"name": "POP3S", "field_data": {"protocol": "tcp", "port": 995}},
            # File / Directory
            {"name": "FTP-Data", "field_data": {"protocol": "tcp", "port": 20}},
            {"name": "FTP-Control", "field_data": {"protocol": "tcp", "port": 21}},
            {"name": "SMB", "field_data": {"protocol": "tcp", "port": 445}},
            {"name": "LDAP", "field_data": {"protocol": "tcp", "port": 389}},
            {"name": "LDAPS", "field_data": {"protocol": "tcp", "port": 636}},
            # Databases
            {"name": "MySQL", "field_data": {"protocol": "tcp", "port": 3306}},
            {"name": "PostgreSQL", "field_data": {"protocol": "tcp", "port": 5432}},
            {"name": "MSSQL", "field_data": {"protocol": "tcp", "port": 1433}},
            {"name": "Redis", "field_data": {"protocol": "tcp", "port": 6379}},
            # Monitoring / Mgmt
            {"name": "SNMP", "field_data": {"protocol": "udp", "port": 161}},
            {"name": "SNMP-Trap", "field_data": {"protocol": "udp", "port": 162}},
            {"name": "Syslog-UDP", "field_data": {"protocol": "udp", "port": 514}},
            {"name": "Syslog-TCP", "field_data": {"protocol": "tcp", "port": 514}},
            {"name": "BGP", "field_data": {"protocol": "tcp", "port": 179}},
            # ICMP
            {"name": "ICMP", "field_data": {"protocol": "icmp"}},
            {"name": "ICMPv6", "field_data": {"protocol": "icmpv6"}},
        ],
    },
    # ── Source / Destination (collapsed into "srcdst") ───────────────────────
    {
        "name": "Addresses",
        "areas": ["source", "destination"],
        "description": "Represents exactly one IP address, prefix, or range.",
        "order_id": 20,
        "display_template": "{name}",
        "field_definitions": [
            {
                "name": "ip_address",
                "type": "object_ref",
                "label": "IP Address",
                "model": "ipam.IPAddress",
                "group_name": "NSM Address",
            },
            {
                "name": "prefix",
                "type": "object_ref",
                "label": "Prefix",
                "model": "ipam.Prefix",
                "group_name": "NSM Address",
            },
            {
                "name": "range",
                "type": "object_ref",
                "label": "Range",
                "model": "ipam.IPRange",
                "group_name": "NSM Address",
            },
            {
                "name": "group",
                "type": "multiobject",
                "label": "Group",
                "description": "Group(s) this address belongs to.",
                "model": "custom-objects.nsm_addresses",
                "group_name": "NSM Address",
            },
        ],
        "default_objects": [],
    },
    {
        "name": "Labels",
        "areas": ["source", "destination"],
        "description": "Logical attribute with type classification.",
        "order_id": 70,
        "display_template": "{label_type}={name}",
        "field_definitions": [
            {
                "name": "label_type",
                "type": "choice",
                "label": "Label Type",
                "choices": ["role", "application", "environment", "location", "custom"],
                "required": True,
                "group_name": "NSM Label",
            },
            {
                "name": "custom_type",
                "type": "text",
                "label": "Custom Type",
                "description": "Required when Label Type = Custom (e.g. 'Department').",
                "group_name": "NSM Label",
            },
            {
                "name": "display_template",
                "type": "text",
                "label": "Display Template",
                "description": "Template string for display, e.g. {label_type}={name}",
                "group_name": "NSM Label",
            },
        ],
        "default_objects": [
            {"name": "dev", "field_data": {"label_type": "environment"}},
            {"name": "test", "field_data": {"label_type": "environment"}},
            {"name": "prod", "field_data": {"label_type": "environment"}},
        ],
    },
    {
        "name": "Zones",
        "areas": ["source", "destination"],
        "description": "Security zone (logical segment of the network).",
        "order_id": 10,
        "display_template": "{name}",
        "field_definitions": [
            {
                "name": "display_template",
                "type": "text",
                "label": "Display Template",
                "description": "Template string for display, e.g. {name}",
                "group_name": "NSM Source/Destination",
            },
        ],
        "default_objects": [
            {"name": "trust", "field_data": {"color": "#2196f3"}},
            {"name": "untrust", "field_data": {"color": "#f44336"}},
            {"name": "dmz", "field_data": {"color": "#fd7e14"}},
            {"name": "mgmt", "field_data": {"color": "#9c27b0"}},
        ],
    },
]
