"""Built-in Custom Type definitions for netbox_nsm.

These types describe the *catalog* that the "Sync built-in types" button on
Setup / sync applies them to ``netbox-custom-objects``. The portable
schema generator (`netbox_nsm.objects.custom_objects_schema`) automatically injects
the following fields into every type, so they MUST NOT be repeated here:

* ``name``        — text, primary, required (id=1, display weight 1)
* ``status``      — select, required, default ``active`` (id=5, weight 2;
                    choices: active, reserved, deprecated)
* ``description`` — text (id=3, weight 90)
* ``comments``    — longtext (id=6, weight 100)
* ``color``       — text (id=7, weight 91)

Custom fields may set ``weight`` (display order) in ``field_definitions``.

IDs 2, 4, 5 (slug / owner_group / owner) are intentionally NOT injected.
Add them explicitly in ``field_definitions`` when needed.

Plus the dynamic-model base contributes ``id``, ``created``, ``last_updated``,
tags, bookmarks, journal entries and subscriptions for free.

Keys used by the schema builder:

* ``name``                — human-readable type name (also slugified for the COT slug)
* ``areas``               — list of section slugs (``source``+``destination``
                           are collapsed into ``srcdst``)
* ``description``         — short description (clipped to 200 chars)
* ``display_template``    — format string stored in ``TypeConfig``
* ``field_definitions``   — list of fields; supported types: ``text``,
                           ``markdown``, ``number``/``integer``, ``boolean``,
                           ``date``, ``json``/``table``, ``choice`` (with
                           ``choices``), ``object_ref`` (with ``model``)
* ``default_objects``     — list of ``{"name": ..., "field_data": {...}}``

UI hints like ``selector``, ``tab_group``, ``visible_when`` and ``__meta__``
markers are intentionally NOT used here — they have no equivalent in the
portable schema and are silently ignored anyway.
"""

# Former setup seed rows for Network App (no longer created; removed on sync/demo seed).
BUNDLED_NETWORK_APP_DEFAULT_NAMES = frozenset(
    {
        "dns",
        "http",
        "ssl",
        "ssh",
        "rdp",
        "smtp",
        "smb",
        "onedrive",
        "teams",
        "zoom",
    }
)

BUILTIN_CUSTOM_TYPES = [
    # ── Action ────────────────────────────────────────────────────────────────
    {
        "name": "Action",
        "areas": ["action"],
        "description": "Policy action for matching traffic in a rule (e.g. permit, deny, drop, reject). Used in rulebook Action columns.",
        "display_template": "{name}",
        "field_definitions": [],
        "default_objects": [
            {"name": "Permit", "field_data": {"status": "active","color": "#28a745"}},
            {"name": "Deny", "field_data": {"status": "active","color": "#dc3545"}},
            {"name": "Drop", "field_data": {"status": "active","color": "#6c757d"}},
        ],
    },
    # ── Service ───────────────────────────────────────────────────────────────
    {
        "name": "Service",
        "areas": ["services"],
        "description": "Represents one network service (protocol + port). Used in rulebook Service columns and Security Panel links.",
        "display_template": "{name} ({protocol}/{port})",
        "field_definitions": [
            {
                "name": "protocol",
                "type": "choice",
                "label": "Protocol",
                "required": True,
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
                "weight": 10,
            },
            {
                "name": "port",
                "type": "integer",
                "label": "Port",
                "description": "Port 0\u201365535 (TCP/UDP/SCTP only).",
                "validation_minimum": 0,
                "validation_maximum": 65535,
                "group_name": "NSM Service",
                "weight": 11,
            },
        ],
        "default_objects": [
            # Web
            {"name": "HTTP", "field_data": {"status": "active","protocol": "tcp", "port": 80}},
            {"name": "HTTPS", "field_data": {"status": "active","protocol": "tcp", "port": 443}},
            {"name": "HTTP-Alt", "field_data": {"status": "active","protocol": "tcp", "port": 8080}},
            {"name": "HTTPS-Alt", "field_data": {"status": "active","protocol": "tcp", "port": 8443}},
            # DNS / NTP
            {"name": "DNS-UDP", "field_data": {"status": "active","protocol": "udp", "port": 53}},
            {"name": "DNS-TCP", "field_data": {"status": "active","protocol": "tcp", "port": 53}},
            {"name": "NTP", "field_data": {"status": "active","protocol": "udp", "port": 123}},
            # Remote access
            {"name": "SSH", "field_data": {"status": "active","protocol": "tcp", "port": 22}},
            {"name": "Telnet", "field_data": {"status": "active","protocol": "tcp", "port": 23}},
            {"name": "RDP", "field_data": {"status": "active","protocol": "tcp", "port": 3389}},
            # Mail
            {"name": "SMTP", "field_data": {"status": "active","protocol": "tcp", "port": 25}},
            {"name": "SMTPS", "field_data": {"status": "active","protocol": "tcp", "port": 465}},
            {"name": "SMTP-STARTTLS", "field_data": {"status": "active","protocol": "tcp", "port": 587}},
            {"name": "IMAP", "field_data": {"status": "active","protocol": "tcp", "port": 143}},
            {"name": "IMAPS", "field_data": {"status": "active","protocol": "tcp", "port": 993}},
            {"name": "POP3", "field_data": {"status": "active","protocol": "tcp", "port": 110}},
            {"name": "POP3S", "field_data": {"status": "active","protocol": "tcp", "port": 995}},
            # File / Directory
            {"name": "FTP-Data", "field_data": {"status": "active","protocol": "tcp", "port": 20}},
            {"name": "FTP-Control", "field_data": {"status": "active","protocol": "tcp", "port": 21}},
            {"name": "SMB", "field_data": {"status": "active","protocol": "tcp", "port": 445}},
            {"name": "LDAP", "field_data": {"status": "active","protocol": "tcp", "port": 389}},
            {"name": "LDAPS", "field_data": {"status": "active","protocol": "tcp", "port": 636}},
            # Databases
            {"name": "MySQL", "field_data": {"status": "active","protocol": "tcp", "port": 3306}},
            {"name": "PostgreSQL", "field_data": {"status": "active","protocol": "tcp", "port": 5432}},
            {"name": "MSSQL", "field_data": {"status": "active","protocol": "tcp", "port": 1433}},
            {"name": "Redis", "field_data": {"status": "active","protocol": "tcp", "port": 6379}},
            # Monitoring / Mgmt
            {"name": "SNMP", "field_data": {"status": "active","protocol": "udp", "port": 161}},
            {"name": "SNMP-Trap", "field_data": {"status": "active","protocol": "udp", "port": 162}},
            {"name": "Syslog-UDP", "field_data": {"status": "active","protocol": "udp", "port": 514}},
            {"name": "Syslog-TCP", "field_data": {"status": "active","protocol": "tcp", "port": 514}},
            {"name": "BGP", "field_data": {"status": "active","protocol": "tcp", "port": 179}},
            # ICMP
            {"name": "ICMP", "field_data": {"status": "active","protocol": "icmp"}},
            {"name": "ICMPv6", "field_data": {"status": "active","protocol": "icmpv6"}},
        ],
    },
    {
        "name": "Service Group",
        "areas": ["services"],
        "description": "Named collection of services. Referenced in rulebook Service columns; members are nsm_service objects.",
        "display_template": "{name}",
        "field_definitions": [
            {
                "name": "group",
                "type": "object_ref",
                "label": "Group Members",
                "model": "custom-objects.nsm_service",
                "group_name": "NSM Service Group",
                "weight": 10,
            },
        ],
        "default_objects": [],
    },
    # ── Source / Destination (collapsed into "srcdst") ───────────────────────
    {
        "name": "Address",
        "areas": ["source", "destination"],
        "description": "Named address object for policy rules (host, prefix, or range). Used in Source/Destination columns and Security Panel links.",
        "display_template": "{name}",
        "field_definitions": [
            {
                "name": "address",
                "type": "object_ref",
                "label": "Address",
                "description": "NetBox IP address, range, or prefix this policy object represents.",
                "required": False,
                "model": [
                    "ipam.IPAddress",
                    "ipam.IPRange",
                    "ipam.Prefix",
                ],
                "weight": 11,
            },
        ],
        "default_objects": [],
    },
    {
        "name": "Address Group",
        "areas": ["source", "destination"],
        "description": "Named collection of address objects. Used in Source/Destination columns; members are nsm_address objects.",
        "display_template": "{name}",
        "field_definitions": [
            {
                "name": "group",
                "type": "object_ref",
                "label": "Group Members",
                "model": "custom-objects.nsm_address",
                "group_name": "NSM Address Group",
                "weight": 10,
            },
        ],
        "default_objects": [],
    },
    {
        "name": "Label",
        "areas": ["source", "destination"],
        "description": "Classification tag for inventory or rules (e.g. compliance, tier). Used in label columns and Security Panel links.",
        "display_template": "{label_type}={name}",
        "field_definitions": [
            {
                "name": "label_type",
                "type": "choice",
                "label": "Label Type",
                "choices": ["role", "application", "environment", "location", "custom"],
                "required": True,
                "group_name": "NSM Label",
                "weight": 10,
            },
        ],
        "default_objects": [
            {"name": "dev", "field_data": {"status": "active","label_type": "environment"}},
            {"name": "test", "field_data": {"status": "active","label_type": "environment"}},
            {"name": "prod", "field_data": {"status": "active","label_type": "environment"}},
        ],
    },
    {
        "name": "Zone",
        "areas": ["source", "destination"],
        "description": "Security zone (logical segment of the network).",
        "display_template": "{name}",
        "field_definitions": [],
        "default_objects": [
            {"name": "trust", "field_data": {"status": "active","color": "#2196f3"}},
            {"name": "untrust", "field_data": {"status": "active","color": "#f44336"}},
            {"name": "dmz", "field_data": {"status": "active","color": "#fd7e14"}},
            {"name": "mgmt", "field_data": {"status": "active","color": "#9c27b0"}},
        ],
    },
    # ── Business App ──────────────────────────────────────────────────────────
    {
        "name": "App Business",
        "areas": ["source", "destination"],
        "description": "Business application with technical and business ownership.",
        "display_template": "{name}",
        "field_definitions": [
            {
                "name": "criticality",
                "type": "choice",
                "label": "Criticality",
                "choices": ["low", "medium", "high", "critical"],
                "weight": 10,
            },
            {
                "name": "business_owner",
                "type": "object_ref",
                "label": "Business Owner",
                "model": "tenancy.ContactGroup",
                "weight": 11,
            },
            {
                "name": "technical_owner",
                "type": "object_ref",
                "label": "Technical Owner",
                "model": "tenancy.ContactGroup",
                "weight": 12,
            },
        ],
        "default_objects": [],
    },
    # ── Network App ───────────────────────────────────────────────────────────
    {
        "name": "App Network",
        "areas": ["source", "destination"],
        "description": "Network application identifier, similar to Palo Alto App-ID (e.g. ssh, onedrive, ssl).",
        "display_template": "{name}",
        "field_definitions": [
            {
                "name": "app_category",
                "type": "text",
                "label": "Category",
                "weight": 10,
            },
            {
                "name": "app_risk",
                "type": "text",
                "label": "Risk Level",
                "description": "Risk level 1 (lowest) to 5 (highest), matching Palo Alto App-ID convention.",
                "weight": 11,
            },
            {
                "name": "default_ports",
                "type": "text",
                "label": "Default Ports",
                "description": "Comma-separated list of default ports/protocols, e.g. tcp/443,tcp/80",
                "weight": 12,
            },
        ],
        "default_objects": [],
    },
    # ── Object Link (COT; sole source of truth for panel links) ───────────────
    {
        "name": "Object Link",
        "areas": [],
        "description": (
            "Links NetBox inventory to an NSM policy object with propagation "
            "semantics. Sole source of truth for Security Panel object links."
        ),
        "display_template": "{name}",
        "field_definitions": [
            {
                "name": "link_type",
                "type": "choice",
                "label": "Link Type",
                "description": (
                    "policy: inventory ↔ policy object with propagation; "
                    "rulebook: device/VM/VDC ↔ deployed rulebook (Security Panel); "
                    "enforcement_point: rulebook enforcement host assignment or interface ↔ NSM object."
                ),
                "required": True,
                "choices": ["policy", "rulebook", "enforcement_point"],
                "group_name": "NSM Object Link",
                "weight": 9,
            },
            {
                "name": "policy_object",
                "type": "object_ref",
                "label": "Policy Object",
                "description": "NSM policy object (zone, address, label, service, …).",
                "required": False,
                "model": [
                    "custom-objects.nsm_zone",
                    "custom-objects.nsm_address",
                    "custom-objects.nsm_address_group",
                    "custom-objects.nsm_label",
                    "custom-objects.nsm_service",
                    "custom-objects.nsm_service_group",
                    "custom-objects.nsm_app_business",
                    "custom-objects.nsm_app_network",
                ],
                "weight": 10,
            },
            {
                "name": "netbox_object",
                "type": "object_ref",
                "label": "NetBox Object",
                "description": (
                    "NetBox inventory object this link is stored on "
                    "(device, VM, interface, prefix, …)."
                ),
                "required": True,
                "model": [
                    "dcim.Device",
                    "virtualization.VirtualMachine",
                    "dcim.VirtualDeviceContext",
                    "dcim.Interface",
                    "virtualization.VMInterface",
                    "ipam.Prefix",
                    "ipam.IPAddress",
                    "ipam.IPRange",
                ],
                "weight": 11,
            },
            {
                "name": "propagation",
                "type": "choice",
                "label": "Propagation",
                "description": (
                    "How the link is stored and inherited to IPAM children "
                    "or group members."
                ),
                "required": False,
                "choices": [
                    "direct",
                    "inherit_ipam",
                    "inherit_ipam_stop",
                    "inherit_group",
                    "inherit_group_stop",
                ],
                "group_name": "NSM Object Link Propagation",
                "weight": 12,
            },
            {
                "name": "rulebook_slug",
                "type": "text",
                "label": "Rulebook Slug",
                "description": (
                    "Deployed COT rulebook slug (nsm_rb_*) when link_type is "
                    "rulebook or enforcement_point."
                ),
                "required": False,
                "weight": 14,
            },
            {
                "name": "comment",
                "type": "markdown",
                "label": "Comment",
                "description": "Optional note shown in the Security Panel link row.",
                "weight": 13,
            },
        ],
        "default_objects": [],
    },
]
