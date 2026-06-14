from netbox.filtersets import NetBoxModelFilterSet
import django_filters
from django.db.models import Q
from django_filters import FilterSet

from netbox_nsm.objects.object_link_service import get_object_link_model

__all__ = ("ObjectLinkFilterSet",)


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
