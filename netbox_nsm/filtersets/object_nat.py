from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import ObjectNAT

__all__ = ("ObjectNATFilterSet",)


@register_filterset
class ObjectNATFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = ObjectNAT
        fields = ("id", "name", "nat_type", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value)
