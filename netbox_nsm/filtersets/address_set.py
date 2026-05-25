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
from virtualization.models import VirtualMachine

from netbox_nsm.models import (
    AddressSet,
    Address,
    SecurityZone,
)

__all__ = (
    "AddressSetFilterSet",
)


@register_filterset
class AddressSetFilterSet(TenancyFilterSet, PrimaryModelFilterSet):
    address_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Address.objects.all(),
        field_name="addresses",
        to_field_name="id",
        label=_("Address (ID)"),
    )
    address = django_filters.ModelMultipleChoiceFilter(
        queryset=Address.objects.all(),
        field_name="addresses__name",
        to_field_name="name",
        label=_("Address (Name)"),
    )
    address_set_id = django_filters.ModelMultipleChoiceFilter(
        queryset=AddressSet.objects.all(),
        field_name="addressset_address_sets",
        to_field_name="id",
        label=_("Address Set (ID)"),
    )
    address_set = django_filters.ModelMultipleChoiceFilter(
        queryset=Address.objects.all(),
        field_name="addressset_address_sets__name",
        to_field_name="name",
        label=_("Address Set (Name)"),
    )

    class Meta:
        model = AddressSet
        fields = ["id", "name", "description", "identifier"]

    def search(self, queryset, name, value):
        """Perform the filtered search."""
        if not value.strip():
            return queryset
        qs_filter = (
            Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(identifier__icontains=value)
        )
        return queryset.filter(qs_filter)
