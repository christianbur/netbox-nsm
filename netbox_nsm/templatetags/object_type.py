from django import template
from netbox.plugins import get_plugin_config

register = template.Library()


@register.simple_tag
def nsm_plugin_setting(name, default=None):
    """Return one netbox-nsm plugin setting (for asset templates)."""
    return get_plugin_config("netbox_nsm", name, default)


@register.filter(name="dict_get")
def dict_get(mapping, key):
    """Return mapping[key] for template dict lookups (e.g. zone_labels|dict_get:zone.pk)."""
    if not mapping:
        return ""
    try:
        return mapping.get(key, "")
    except AttributeError:
        return ""
