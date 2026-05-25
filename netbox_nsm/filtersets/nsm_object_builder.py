from django.db.models import Q

from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import NsmObjectType, NsmObjectTypeField, NsmObject

__all__ = (
    "NsmObjectTypeFilterSet",
    "NsmObjectTypeFieldFilterSet",
    "NsmObjectFilterSet",
)


@register_filterset
class NsmObjectTypeFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = NsmObjectType
        fields = ("id", "name", "slug", "group_name", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(slug__icontains=value)
            | Q(group_name__icontains=value)
            | Q(description__icontains=value)
        )


@register_filterset
class NsmObjectTypeFieldFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = NsmObjectTypeField
        fields = ("id", "nsm_object_type", "name", "type", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(label__icontains=value)
            | Q(description__icontains=value)
            | Q(nsm_object_type__name__icontains=value)
        )


@register_filterset
class NsmObjectFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = NsmObject
        fields = ("id", "nsm_object_type", "name", "source_model", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(source_model__icontains=value)
            | Q(nsm_object_type__name__icontains=value)
        )
