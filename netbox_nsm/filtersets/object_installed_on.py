from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import ObjectInstalledOn

__all__ = ("ObjectInstalledOnFilterSet",)


@register_filterset
class ObjectInstalledOnFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = ObjectInstalledOn
        fields = ("id", "name", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value)
