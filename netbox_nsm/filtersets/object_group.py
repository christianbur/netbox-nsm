import django_filters
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from dcim.models import Device, VirtualDeviceContext
from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset
from utilities.filters import MultiValueCharFilter, MultiValueNumberFilter
from virtualization.models import VirtualMachine

from netbox_nsm.models import ObjectGroup

__all__ = ("ObjectGroupFilterSet",)


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
