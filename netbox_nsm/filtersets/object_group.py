import django_filters
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from dcim.models import Device, VirtualDeviceContext
from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset
from utilities.filters import MultiValueCharFilter, MultiValueNumberFilter
from virtualization.models import VirtualMachine

from netbox_nsm.mixins import AssignmentFilterSet
from netbox_nsm.models import ObjectGroup, ObjectGroupAssignment

__all__ = ("ObjectGroupFilterSet", "ObjectGroupAssignmentFilterSet")


@register_filterset
class ObjectGroupFilterSet(PrimaryModelFilterSet):
    group_type = django_filters.MultipleChoiceFilter(
        choices=ObjectGroup._meta.get_field("group_type").choices,
        method="filter_group_type",
    )

    class Meta:
        model = ObjectGroup
        fields = ("id", "name", "group_type", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))

    def filter_group_type(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(group_type__in=value)


@register_filterset
class ObjectGroupAssignmentFilterSet(AssignmentFilterSet):
    group_id = django_filters.ModelMultipleChoiceFilter(
        queryset=ObjectGroup.objects.all(),
        label=_("Group (ID)"),
    )
    device = MultiValueCharFilter(
        method="filter_device",
        field_name="name",
        label=_("Device (name)"),
    )
    device_id = MultiValueNumberFilter(
        method="filter_device",
        field_name="pk",
        label=_("Device (ID)"),
    )
    virtualdevicecontext = MultiValueCharFilter(
        method="filter_virtualdevicecontext",
        field_name="name",
        label=_("Virtual Device Context (name)"),
    )
    virtualdevicecontext_id = MultiValueNumberFilter(
        method="filter_virtualdevicecontext",
        field_name="pk",
        label=_("Virtual Device Context (ID)"),
    )
    virtualmachine = MultiValueCharFilter(
        method="filter_virtual_machine",
        field_name="name",
        label=_("Virtual Machine (name)"),
    )
    virtualmachine_id = MultiValueNumberFilter(
        method="filter_virtual_machine",
        field_name="pk",
        label=_("Virtual Machine (ID)"),
    )

    class Meta:
        model = ObjectGroupAssignment
        fields = ("id", "group_id", "assigned_object_type", "assigned_object_id")

    def filter_device(self, queryset, name, value):
        if not (devices := Device.objects.filter(**{f"{name}__in": value})).exists():
            return queryset.none()
        return queryset.filter(
            assigned_object_type=ContentType.objects.get_for_model(Device),
            assigned_object_id__in=devices.values_list("id", flat=True),
        )

    def filter_virtualdevicecontext(self, queryset, name, value):
        if not (
            devices := VirtualDeviceContext.objects.filter(**{f"{name}__in": value})
        ).exists():
            return queryset.none()
        return queryset.filter(
            assigned_object_type=ContentType.objects.get_for_model(VirtualDeviceContext),
            assigned_object_id__in=devices.values_list("id", flat=True),
        )

    def filter_virtual_machine(self, queryset, name, value):
        if not (
            devices := VirtualMachine.objects.filter(**{f"{name}__in": value})
        ).exists():
            return queryset.none()
        return queryset.filter(
            assigned_object_type=ContentType.objects.get_for_model(VirtualMachine),
            assigned_object_id__in=devices.values_list("id", flat=True),
        )
