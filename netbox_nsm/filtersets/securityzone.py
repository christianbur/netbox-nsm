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

from dcim.models import Interface, Device, VirtualDeviceContext
from virtualization.models import VirtualMachine

from netbox_nsm.models import (
    SecurityZone,
)

__all__ = (
    "SecurityZoneFilterSet",
)


@register_filterset
class SecurityZoneFilterSet(TenancyFilterSet, PrimaryModelFilterSet):
    prefix_id = MultiValueNumberFilter(
        method="filter_prefix",
        label=_("Prefix (ID)"),
    )
    ip_address_id = MultiValueNumberFilter(
        method="filter_ip_address",
        label=_("IP Address (ID)"),
    )
    ip_range_id = MultiValueNumberFilter(
        method="filter_ip_range",
        label=_("IP Range (ID)"),
    )

    class Meta:
        model = SecurityZone
        fields = [
            "id",
            "name",
            "color",
            "description",
            "prefix_id",
            "ip_address_id",
            "ip_range_id",
        ]

    def search(self, queryset, name, value):
        """Perform the filtered search."""
        if not value.strip():
            return queryset
        qs_filter = (
            Q(name__icontains=value)
            | Q(color__icontains=value)
            | Q(description__icontains=value)
        )
        return queryset.filter(qs_filter)

    def _filter_by_assigned_object(self, queryset, value, app_label, model):
        """Filter SecurityZones by Addresses assigned to objects of a given type."""
        if not value:
            return queryset
        return queryset.filter(
            addresses__address__assigned_object_type__app_label=app_label,
            addresses__address__assigned_object_type__model=model,
            addresses__address__assigned_object_id__in=value,
        ).distinct()

    def filter_prefix(self, queryset, name, value):
        return self._filter_by_assigned_object(queryset, value, "ipam", "prefix")

    def filter_ip_address(self, queryset, name, value):
        return self._filter_by_assigned_object(queryset, value, "ipam", "ipaddress")

    def filter_ip_range(self, queryset, name, value):
        return self._filter_by_assigned_object(queryset, value, "ipam", "iprange")
