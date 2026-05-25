import django_filters
from django.db.models import Q

from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import ObjectCustomType

__all__ = ("ObjectCustomTypeFilterSet",)


@register_filterset
class ObjectCustomTypeFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = ObjectCustomType
        fields = ("id", "name", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(description__icontains=value)
        )
