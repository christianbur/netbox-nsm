from django.db.models import Q

from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import ObjectLog

__all__ = ("ObjectLogFilterSet",)


@register_filterset
class ObjectLogFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = ObjectLog
        fields = ("id", "name", "enabled", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value)
        )
