import django_filters

from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import SecurityObjectGroup

__all__ = ("SecurityObjectGroupFilterSet",)


@register_filterset
class SecurityObjectGroupFilterSet(PrimaryModelFilterSet):
    area_id = django_filters.NumberFilter(field_name="areas")

    class Meta:
        model = SecurityObjectGroup
        fields = ("id", "name", "area_id")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value)
