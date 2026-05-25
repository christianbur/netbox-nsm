import django_filters
from django.utils.translation import gettext_lazy as _

from utilities.filtersets import register_filterset

from netbox_nsm.mixins import AssignmentFilterSet
from netbox_nsm.models import ObjectCustomObject, ObjectCustomObjectAssignment

__all__ = ("ObjectCustomObjectAssignmentFilterSet",)


@register_filterset
class ObjectCustomObjectAssignmentFilterSet(AssignmentFilterSet):
    custom_object_id = django_filters.ModelMultipleChoiceFilter(
        queryset=ObjectCustomObject.objects.all(),
        label=_("Custom Object (ID)"),
    )

    class Meta:
        model = ObjectCustomObjectAssignment
        fields = ("id", "custom_object_id", "assigned_object_type", "assigned_object_id")
