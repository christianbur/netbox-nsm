from django import template

register = template.Library()


@register.filter(name="dict_get")
def dict_get(mapping, key):
    """Return mapping[key] for template dict lookups (e.g. zone_labels|dict_get:zone.pk)."""
    if not mapping:
        return ""
    try:
        return mapping.get(key, "")
    except AttributeError:
        return ""
