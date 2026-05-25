import django_filters
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from netbox.filtersets import NetBoxModelFilterSet
from utilities.filtersets import register_filterset
from utilities.filters import (
    ContentTypeFilter,
    MultiValueCharFilter,
    MultiValueNumberFilter,
)

from dcim.models import Device, VirtualDeviceContext
from virtualization.models import VirtualMachine

from netbox_nsm.models import (
    AddressList,
    Address,
    AddressSet,
    SecurityZone,
)

__all__ = (
    "AddressListFilterSet",
)


@register_filterset
class AddressListFilterSet(NetBoxModelFilterSet):
    assigned_object_type = ContentTypeFilter()
    address = MultiValueCharFilter(
        method="filter_address",
        field_name="name",
        label=_("Address (name)"),
    )
    address_id = MultiValueNumberFilter(
        method="filter_address",
        field_name="pk",
        label=_("Address (ID)"),
    )
    addressset = MultiValueCharFilter(
        method="filter_addressset",
        field_name="name",
        label=_("Address Set (name)"),
    )
    addressset_id = MultiValueNumberFilter(
        method="filter_addressset",
        field_name="pk",
        label=_("Address Set (ID)"),
    )
    class Meta:
        model = AddressList
        fields = ["id", "assigned_object_type", "assigned_object_id"]

    def search(self, queryset, name, value):
        """Perform the filtered search."""
        if not value.strip():
            return queryset
        qs_filter = Q(name__icontains=value)
        return queryset.filter(qs_filter)

    def filter_address(self, queryset, name, value):
        if not (addresses := Address.objects.filter(**{f"{name}__in": value})).exists():
            return queryset.none()
        return queryset.filter(
            assigned_object_type=ContentType.objects.get_for_model(Address),
            assigned_object_id__in=addresses.values_list("id", flat=True),
        )

    def filter_addressset(self, queryset, name, value):
        if not (
            addresses := AddressSet.objects.filter(**{f"{name}__in": value})
        ).exists():
            return queryset.none()
        return queryset.filter(
            assigned_object_type=ContentType.objects.get_for_model(AddressSet),
            assigned_object_id__in=addresses.values_list("id", flat=True),
        )


@register_filterset
