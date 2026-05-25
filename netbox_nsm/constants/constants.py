"""
Constants for filters
"""

from django.db.models import Q

ADDRESS_FIELD_ASSIGNMENT_MODELS = Q(
    Q(app_label="ipam", model="prefix")
    | Q(app_label="ipam", model="iprange")
    | Q(app_label="ipam", model="ipaddress")
    | Q(app_label="netbox_nsm", model="customprefix")
)

ADDRESS_LIST_ASSIGNMENT_MODELS = Q(
    Q(app_label="netbox_nsm", model="address")
    | Q(app_label="netbox_nsm", model="addressset")
)

RULESET_ASSIGNMENT_MODELS = Q(
    Q(app_label="dcim", model="device")
    | Q(app_label="dcim", model="virtualdevicecontext")
    | Q(app_label="virtualization", model="virtualmachine")
)

POOL_ASSIGNMENT_MODELS = Q(
    Q(app_label="dcim", model="device")
    | Q(app_label="dcim", model="virtualdevicecontext")
    | Q(app_label="virtualization", model="virtualmachine")
)

RULE_ASSIGNMENT_MODELS = Q(Q(app_label="dcim", model="interface"))

ZONE_ASSIGNMENT_MODELS = Q(
    Q(app_label="dcim", model="device")
    | Q(app_label="dcim", model="virtualdevicecontext")
    | Q(app_label="dcim", model="interface")
    | Q(app_label="virtualization", model="virtualmachine")
)

ADDRESS_ASSIGNMENT_MODELS = Q(
    Q(app_label="dcim", model="device")
    | Q(app_label="dcim", model="virtualdevicecontext")
    | Q(app_label="virtualization", model="virtualmachine")
    | Q(app_label="netbox_nsm", model="securityzone")
)

OBJECT_ASSIGNMENT_MODELS = Q()  # No restriction — allow all NetBox object types

FILTER_ASSIGNMENT_MODELS = Q(
    Q(app_label="dcim", model="device")
    | Q(app_label="dcim", model="virtualdevicecontext")
    | Q(app_label="virtualization", model="virtualmachine")
)

FILTER_SETTING_ASSIGNMENT_MODELS = Q(
    Q(app_label="netbox_nsm", model="firewallfilterrule")
)

POLICER_ASSIGNMENT_MODELS = Q(
    Q(app_label="dcim", model="device")
    | Q(app_label="dcim", model="virtualdevicecontext")
    | Q(app_label="virtualization", model="virtualmachine")
)

APPLICATION_ASSIGNMENT_MODELS = Q(
    Q(app_label="dcim", model="device")
    | Q(app_label="dcim", model="virtualdevicecontext")
    | Q(app_label="virtualization", model="virtualmachine")
)
