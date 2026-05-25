from django import template
from ipam.models import Prefix, IPAddress, IPRange

register = template.Library()


@register.simple_tag(name="get_related_object_type")
def get_related_object_type(obj):
    if type(obj) is Prefix:
        obj_type = "Prefix"
    elif type(obj) is IPAddress:
        obj_type = "IP Address"
    elif type(obj) is IPRange:
        obj_type = "IP Range"
    else:
        return None
    return obj_type
