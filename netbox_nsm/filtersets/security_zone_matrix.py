import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import SecurityZoneMatrix, SecurityZoneRole

__all__ = ("SecurityZoneMatrixFilterSet",)


@register_filterset
class SecurityZoneMatrixFilterSet(PrimaryModelFilterSet):
    role_id = django_filters.ModelMultipleChoiceFilter(
        field_name="roles",
        queryset=SecurityZoneRole.objects.all(),
        to_field_name="id",
        label=_("Security Zone Role (ID)"),
    )

    class Meta:
        model = SecurityZoneMatrix
        fields = ("id", "name", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = Q(name__icontains=value) | Q(description__icontains=value)
        return queryset.filter(qs_filter)
