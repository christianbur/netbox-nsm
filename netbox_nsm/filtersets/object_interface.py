from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import ObjectInterface

__all__ = ("ObjectInterfaceFilterSet",)


@register_filterset
class ObjectInterfaceFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = ObjectInterface
        fields = ("id", "name", "direction", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value)
