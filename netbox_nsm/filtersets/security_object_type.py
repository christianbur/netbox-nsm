import django_filters
from django.db.models import Q

from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import SecurityObjectType

__all__ = ("SecurityObjectTypeFilterSet",)


@register_filterset
class SecurityObjectTypeFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = SecurityObjectType
        fields = ("id", "name", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(description__icontains=value)
        )
