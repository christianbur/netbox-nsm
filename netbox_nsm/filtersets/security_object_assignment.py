import django_filters
from django.utils.translation import gettext_lazy as _

from utilities.filtersets import register_filterset

from netbox_nsm.mixins import AssignmentFilterSet
from netbox_nsm.models import SecurityObject, SecurityObjectAssignment

__all__ = ("SecurityObjectAssignmentFilterSet",)


@register_filterset
class SecurityObjectAssignmentFilterSet(AssignmentFilterSet):
    custom_object_id = django_filters.ModelMultipleChoiceFilter(
        queryset=SecurityObject.objects.all(),
        label=_("Custom Object (ID)"),
    )

    class Meta:
        model = SecurityObjectAssignment
        fields = ("id", "custom_object_id", "assigned_object_type", "assigned_object_id")
