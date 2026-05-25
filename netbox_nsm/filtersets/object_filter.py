from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import ObjectFilter

__all__ = ("ObjectFilterFilterSet",)


@register_filterset
class ObjectFilterFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = ObjectFilter
        fields = ("id", "name", "family", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value)
