from django.db.models import Q

from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import SecurityPropertyType, SecurityPropertyField, SecurityProperty

__all__ = (
    "SecurityPropertyTypeFilterSet",
    "SecurityPropertyFieldFilterSet",
    "SecurityPropertyFilterSet",
)


@register_filterset
class SecurityPropertyTypeFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = SecurityPropertyType
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
class SecurityPropertyFieldFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = SecurityPropertyField
        fields = ("id", "security_property_type", "name", "type", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(label__icontains=value)
            | Q(description__icontains=value)
            | Q(security_property_type__name__icontains=value)
        )


@register_filterset
class SecurityPropertyFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = SecurityProperty
        fields = ("id", "security_property_type", "name", "source_model", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(source_model__icontains=value)
            | Q(security_property_type__name__icontains=value)
        )
