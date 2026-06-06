from django import template

from netbox_nsm.ag_grid_vendor import (
    AG_GRID_COMMUNITY_VERSION,
    ag_grid_community_license_label as _license_label,
)

register = template.Library()


@register.simple_tag
def ag_grid_community_version() -> str:
    return AG_GRID_COMMUNITY_VERSION


@register.simple_tag
def ag_grid_community_license_label() -> str:
    return _license_label()
