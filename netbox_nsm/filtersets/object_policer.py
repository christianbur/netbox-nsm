from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import ObjectPolicer

__all__ = ("ObjectPolicerFilterSet",)


@register_filterset
class ObjectPolicerFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = ObjectPolicer
        fields = ("id", "name", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value)
