import django_filters
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from netbox.filtersets import PrimaryModelFilterSet
from tenancy.filtersets import TenancyFilterSet
from utilities.filtersets import register_filterset
from utilities.filters import (
    MultiValueCharFilter,
    MultiValueNumberFilter,
)

from dcim.models import Device, VirtualDeviceContext
from ipam.models import IPRange, Prefix, IPAddress
from virtualization.models import VirtualMachine

from netbox_nsm.models import (
    Address,
    CustomPrefix,
    AddressSet,
    SecurityZone,
)

__all__ = (
    "AddressFilterSet",
)


@register_filterset
class AddressFilterSet(TenancyFilterSet, PrimaryModelFilterSet):
    assigned_object_id = MultiValueNumberFilter(
        field_name="assigned_object_id",
        label=_("Assigned Object (ID)"),
    )
    assigned_object_type_id = django_filters.ModelMultipleChoiceFilter(
        field_name="assigned_object_type",
        queryset=ContentType.objects.all(),
        to_field_name="id",
        label=_("Assigned Object Type (ID)"),
    )
    assigned_object_type = django_filters.ModelMultipleChoiceFilter(
        field_name="assigned_object_type__model",
        queryset=ContentType.objects.all(),
        to_field_name="model",
        label=_("Assigned Object Type (Model)"),
    )
    address_set_id = django_filters.ModelMultipleChoiceFilter(
        queryset=AddressSet.objects.all(),
        field_name="addressset_addresses",
        to_field_name="id",
        label=_("Address Set (ID)"),
    )
    custom_prefix_id = django_filters.ModelMultipleChoiceFilter(
        field_name="custom_prefixes",
        queryset=CustomPrefix.objects.all(),
        label=_("Custom Prefix (ID)"),
    )
    custom_prefix = django_filters.ModelMultipleChoiceFilter(
        field_name="custom_prefixes__prefix",
        queryset=CustomPrefix.objects.all(),
        to_field_name="prefix",
        label=_("Custom Prefix (Prefix)"),
    )
    # Aliases for reverse GenericRelation field names used by filter coverage tests.
    custom_prefixes = django_filters.ModelMultipleChoiceFilter(
        field_name="custom_prefixes",
        queryset=CustomPrefix.objects.all(),
        label=_("Custom Prefixes"),
    )
    prefix_id = django_filters.ModelMultipleChoiceFilter(
        field_name="prefixes",
        queryset=Prefix.objects.all(),
        label=_("Prefix (ID)"),
    )
    prefix = django_filters.ModelMultipleChoiceFilter(
        field_name="prefixes__prefix",
        queryset=Prefix.objects.all(),
        to_field_name="prefix",
        label=_("Prefix (Name)"),
    )
    prefixes = django_filters.ModelMultipleChoiceFilter(
        field_name="prefixes",
        queryset=Prefix.objects.all(),
        label=_("Prefixes"),
    )
    ip_address_id = django_filters.ModelMultipleChoiceFilter(
        field_name="ip_addresses",
        queryset=IPAddress.objects.all(),
        label=_("IP Address (ID)"),
    )
    ip_address = django_filters.ModelMultipleChoiceFilter(
        field_name="ip_addresses__address",
        queryset=IPAddress.objects.all(),
        to_field_name="address",
        label=_("IP Address (Address)"),
    )
    ip_addresses = django_filters.ModelMultipleChoiceFilter(
        field_name="ip_addresses",
        queryset=IPAddress.objects.all(),
        label=_("IP Addresses"),
    )
    ip_range_id = django_filters.ModelMultipleChoiceFilter(
        field_name="ip_ranges",
        queryset=IPRange.objects.all(),
        to_field_name="id",
        label=_("IPRange (ID)"),
    )
    ip_range = django_filters.ModelMultipleChoiceFilter(
        field_name="ip_ranges__start_address",
        queryset=IPRange.objects.all(),
        to_field_name="start_address",
        label=_("IPRange (Start Address)"),
    )
    ip_ranges = django_filters.ModelMultipleChoiceFilter(
        field_name="ip_ranges",
        queryset=IPRange.objects.all(),
        label=_("IP Ranges"),
    )

    class Meta:
        model = Address
        fields = ["id", "name", "description", "dns_name"]

    def search(self, queryset, name, value):
        """Perform the filtered search."""
        if not value.strip():
            return queryset
        qs_filter = (
            Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(dns_name=value)
        )
        return queryset.filter(qs_filter)


@register_filterset
