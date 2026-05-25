import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from netbox.filtersets import NetBoxModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import (
    SecurityZone,
    SecurityZoneMatrix,
    SecurityZoneMatrixCell,
    SecurityZoneMatrixPolicy,
)

__all__ = ("SecurityZoneMatrixCellFilterSet",)


@register_filterset
class SecurityZoneMatrixCellFilterSet(NetBoxModelFilterSet):
    matrix_id = django_filters.ModelMultipleChoiceFilter(
        field_name="matrix",
        queryset=SecurityZoneMatrix.objects.all(),
        to_field_name="id",
        label=_("Security Zone Matrix (ID)"),
    )
    source_zone_id = django_filters.ModelMultipleChoiceFilter(
        field_name="source_zone",
        queryset=SecurityZone.objects.all(),
        to_field_name="id",
        label=_("Source Zone (ID)"),
    )
    destination_zone_id = django_filters.ModelMultipleChoiceFilter(
        field_name="destination_zone",
        queryset=SecurityZone.objects.all(),
        to_field_name="id",
        label=_("Destination Zone (ID)"),
    )
    policy_id = django_filters.ModelMultipleChoiceFilter(
        field_name="policy",
        queryset=SecurityZoneMatrixPolicy.objects.all(),
        to_field_name="id",
        label=_("Security Zone Matrix Policy (ID)"),
    )

    class Meta:
        model = SecurityZoneMatrixCell
        fields = (
            "id",
            "matrix_id",
            "source_zone_id",
            "destination_zone_id",
            "policy_id",
        )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = (
            Q(matrix__name__icontains=value)
            | Q(source_zone__name__icontains=value)
            | Q(destination_zone__name__icontains=value)
            | Q(policy__name__icontains=value)
        )
        return queryset.filter(qs_filter)
