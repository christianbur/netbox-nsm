import django_filters

from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import ObjectCustomObject

__all__ = ("ObjectCustomObjectFilterSet",)


@register_filterset
class ObjectCustomObjectFilterSet(PrimaryModelFilterSet):
    custom_type_id = django_filters.NumberFilter(field_name="custom_type__id")

    class Meta:
        model = ObjectCustomObject
        fields = ("id", "name", "custom_type_id", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value)
