"""Shared TypeConfig definitions for Setup, sync, and demos."""

__all__ = (
    "REQUIRED_COT_SLUGS",
    "RULEBOOK_TEMPLATE_SLUGS",
    "TYPECONFIG_SPECS",
    "TYPECONFIG_SPEC_BY_SLUG",
)

REQUIRED_COT_SLUGS = [
    "nsm_action",
    "nsm_service",
    "nsm_service_group",
    "nsm_address",
    "nsm_address_group",
    "nsm_label",
    "nsm_zone",
    "nsm_app_business",
    "nsm_app_network",
    "nsm_object_link",
]

from netbox_nsm.rulebooks.templates import RULEBOOK_TEMPLATE_SLUGS  # noqa: E402

TYPECONFIG_SPECS = [
    {
        "slug": "nsm_zone",
        "label": "Zones",
        "matching_class": "zone",
        "display_template": "{name}",
        "panel_linkable_types": [],
    },
    {
        "slug": "nsm_address",
        "label": "Addresses",
        "matching_class": "address",
        "display_template": "{name}",
        "panel_linkable_types": [],
    },
    {
        "slug": "nsm_address_group",
        "label": "Address Groups",
        "matching_class": "address",
        "display_template": "{name}",
        "panel_linkable_types": [],
    },
    {
        "slug": "nsm_label",
        "label": "Labels",
        "matching_class": "label",
        "display_template": "{label_type[0]!u}:{name}",
        "panel_linkable_types": [],
    },
    {
        "slug": "nsm_service",
        "label": "Services",
        "matching_class": "service",
        "display_template": "{name} ({protocol}/{port})",
        "panel_linkable_types": [],
    },
    {
        "slug": "nsm_service_group",
        "label": "Service Groups",
        "matching_class": "service",
        "display_template": "{name}",
        "panel_linkable_types": [],
    },
    {
        "slug": "nsm_action",
        "label": "Action",
        "matching_class": "action",
        "display_template": "{name!u}",
        "panel_linkable_types": [],
    },
    {
        "slug": "nsm_app_business",
        "label": "Business Apps",
        "matching_class": "info",
        "display_template": "{name}",
        "panel_linkable_types": [],
    },
    {
        "slug": "nsm_app_network",
        "label": "Network Apps",
        "matching_class": "application",
        "display_template": "{name}",
        "panel_linkable_types": [],
    },
    {
        "slug": "nsm_object_link",
        "label": "Object Links",
        "matching_class": "other",
        "display_template": "{name}",
        "panel_linkable_types": [],
    },
]

TYPECONFIG_SPEC_BY_SLUG = {spec["slug"]: spec for spec in TYPECONFIG_SPECS}
