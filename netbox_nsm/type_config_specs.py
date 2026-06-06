"""Shared TypeConfig definitions for Setup, sync, and demos."""

__all__ = ("REQUIRED_COT_SLUGS", "TYPECONFIG_SPECS", "TYPECONFIG_SPEC_BY_SLUG")

REQUIRED_COT_SLUGS = [
    "nsm_zones",
    "nsm_addresses",
    "nsm_labels",
    "nsm_services",
    "nsm_action",
    "nsm_business_apps",
    "nsm_network_apps",
]

TYPECONFIG_SPECS = [
    {
        "slug": "nsm_zones",
        "label": "Zones",
        "matching_class": "zone",
        "display_template": "{name}",
        "panel_slugs": ["source", "destination"],
        "order_id": 10,
        "panel_linkable_types": [],
    },
    {
        "slug": "nsm_addresses",
        "label": "Addresses",
        "matching_class": "address",
        "display_template": "{name}",
        "panel_slugs": ["source", "destination"],
        "order_id": 20,
        "panel_linkable_types": [],
    },
    {
        "slug": "nsm_labels",
        "label": "Labels",
        "matching_class": "label",
        "display_template": "{label_type[0]!u}:{name}",
        "panel_slugs": ["source", "destination"],
        "order_id": 30,
        "panel_linkable_types": [],
    },
    {
        "slug": "nsm_services",
        "label": "Services",
        "matching_class": "service",
        "display_template": "{name} ({protocol}/{port})",
        "panel_slugs": ["services"],
        "order_id": 100,
        "panel_linkable_types": [],
    },
    {
        "slug": "nsm_action",
        "label": "Action",
        "matching_class": "action",
        "display_template": "{name!u}",
        "panel_slugs": ["action"],
        "order_id": 200,
        "panel_linkable_types": [],
    },
    {
        "slug": "nsm_business_apps",
        "label": "Business Apps",
        "matching_class": "info",
        "display_template": "{name}",
        "panel_slugs": ["info"],
        "order_id": 110,
        "panel_linkable_types": [],
    },
    {
        "slug": "nsm_network_apps",
        "label": "Network Apps",
        "matching_class": "application",
        "display_template": "{name}",
        "panel_slugs": ["services"],
        "order_id": 110,
        "panel_linkable_types": [],
    },
]

TYPECONFIG_SPEC_BY_SLUG = {spec["slug"]: spec for spec in TYPECONFIG_SPECS}
