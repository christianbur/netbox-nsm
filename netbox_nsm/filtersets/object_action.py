import django_filters
from django.db.models import Q

from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import ObjectAction

__all__ = ("ObjectActionFilterSet",)


@register_filterset
class ObjectActionFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = ObjectAction
        fields = ("id", "name", "action", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(action__icontains=value)
            | Q(description__icontains=value)
        )
