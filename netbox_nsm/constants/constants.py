"""ContentType filters for NSM models."""

from django.db.models import Q

RULESET_ASSIGNMENT_MODELS = Q(
    Q(app_label="dcim", model="device")
    | Q(app_label="dcim", model="virtualdevicecontext")
    | Q(app_label="virtualization", model="virtualmachine")
)
