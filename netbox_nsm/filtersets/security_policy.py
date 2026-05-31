import django_filters
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from dcim.models import Device, VirtualDeviceContext
from netbox.filtersets import NetBoxModelFilterSet, PrimaryModelFilterSet
from utilities.filters import MultiValueCharFilter, MultiValueNumberFilter
from utilities.filtersets import register_filterset
from virtualization.models import VirtualMachine

from netbox_nsm.mixins import AssignmentFilterSet
from netbox_nsm.models import (
    SecurityPolicyRule,
    SecurityPolicyRulebook,
    SecurityPolicyAssignment,
)

__all__ = (
    "SecurityPolicyRulebookFilterSet",
    "SecurityPolicyRuleFilterSet",
    "SecurityPolicyAssignmentFilterSet",
)


@register_filterset
class SecurityPolicyRulebookFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = SecurityPolicyRulebook
        fields = ("id", "name", "rulebook_type", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value)
        )


@register_filterset
class SecurityPolicyRuleFilterSet(PrimaryModelFilterSet):
    rulebook_id = django_filters.ModelMultipleChoiceFilter(
        queryset=SecurityPolicyRulebook.objects.all(),
        field_name="rulebook",
        to_field_name="id",
        label=_("Rulebook (ID)"),
    )

    class Meta:
        model = SecurityPolicyRule
        fields = ("id", "name", "policy_action", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value)
        )


@register_filterset
class SecurityPolicyAssignmentFilterSet(AssignmentFilterSet):
    rulebook_id = django_filters.ModelMultipleChoiceFilter(
        queryset=SecurityPolicyRulebook.objects.all(),
        label=_("Rulebook (ID)"),
    )
    rulebook = django_filters.ModelMultipleChoiceFilter(
        field_name="rulebook__name",
        queryset=SecurityPolicyRulebook.objects.all(),
        to_field_name="name",
        label=_("Rulebook (Name)"),
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
        model = SecurityPolicyAssignment
        fields = ("id", "rulebook_id", "assigned_object_type", "assigned_object_id")

    def filter_device(self, queryset, name, value):
        if not (devices := Device.objects.filter(**{f"{name}__in": value})).exists():
            return queryset.none()
        return queryset.filter(
            assigned_object_type=ContentType.objects.get_for_model(Device),
            assigned_object_id__in=devices.values_list("id", flat=True),
        )

    def filter_virtualdevicecontext(self, queryset, name, value):
        if not (
            vdcs := VirtualDeviceContext.objects.filter(**{f"{name}__in": value})
        ).exists():
            return queryset.none()
        return queryset.filter(
            assigned_object_type=ContentType.objects.get_for_model(
                VirtualDeviceContext
            ),
            assigned_object_id__in=vdcs.values_list("id", flat=True),
        )

    def filter_virtual_machine(self, queryset, name, value):
        if not (
            vms := VirtualMachine.objects.filter(**{f"{name}__in": value})
        ).exists():
            return queryset.none()
        return queryset.filter(
            assigned_object_type=ContentType.objects.get_for_model(VirtualMachine),
            assigned_object_id__in=vms.values_list("id", flat=True),
        )
