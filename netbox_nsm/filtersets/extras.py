import django_filters
from django.db.models import Q
from django_filters import FilterSet

from netbox.filtersets import NetBoxModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import MatchingClassChoices, TypeConfig
from netbox_nsm.objects.object_link_service import get_object_link_model

__all__ = (
    "ObjectLinkFilterSet",
    "TypeConfigFilterSet",
)


class ObjectLinkFilterSet(FilterSet):
    """Filter COT ``nsm_object_link`` rows (legacy API parameter names)."""

    object_a_type_id = django_filters.NumberFilter(
        field_name="netbox_object_content_type_id",
        label="Object A Type (ID)",
    )
    object_b_type_id = django_filters.NumberFilter(
        field_name="policy_object_content_type_id",
        label="Object B Type (ID)",
    )
    object_a_id = django_filters.NumberFilter(
        field_name="netbox_object_object_id",
        label="Object A (ID)",
    )
    object_b_id = django_filters.NumberFilter(
        field_name="policy_object_object_id",
        label="Object B (ID)",
    )
    q = django_filters.CharFilter(method="search", label="Search")

    class Meta:
        fields = (
            "id",
            "object_a_type_id",
            "object_a_id",
            "object_b_type_id",
            "object_b_id",
        )

    def __init__(self, *args, **kwargs):
        model = get_object_link_model()
        if model is not None:
            kwargs.setdefault("queryset", model.objects.all())
        super().__init__(*args, **kwargs)

    def search(self, queryset, name, value):
        if queryset is None or not value.strip():
            return queryset
        return queryset.filter(
            Q(comment__icontains=value) | Q(name__icontains=value)
        )


@register_filterset
class TypeConfigFilterSet(NetBoxModelFilterSet):
    matching_class = django_filters.MultipleChoiceFilter(
        choices=MatchingClassChoices.choices,
    )

    class Meta:
        model = TypeConfig
        fields = ("id", "matching_class")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(content_type__app_label__icontains=value)
            | Q(content_type__model__icontains=value)
        )
