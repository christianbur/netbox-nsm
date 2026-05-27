import django_filters

from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import SecurityObject

__all__ = ("SecurityObjectFilterSet",)


@register_filterset
class SecurityObjectFilterSet(PrimaryModelFilterSet):
    custom_type_id = django_filters.NumberFilter(field_name="custom_type__id")
    area = django_filters.CharFilter(field_name="custom_type__area")

    class Meta:
        model = SecurityObject
        fields = ("id", "name", "custom_type_id", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value)
