import django_filters

from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import SecurityArea

__all__ = ("SecurityAreaFilterSet",)


@register_filterset
class SecurityAreaFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = SecurityArea
        fields = ("id", "slug", "name", "sort_order")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value) | queryset.filter(
            slug__icontains=value
        )
