import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import SecurityZoneMatrixPolicy

__all__ = ("SecurityZoneMatrixPolicyFilterSet",)


@register_filterset
class SecurityZoneMatrixPolicyFilterSet(PrimaryModelFilterSet):
    action = django_filters.CharFilter(field_name="action", label=_("Action"))
    color = django_filters.CharFilter(field_name="color", label=_("Color"))

    class Meta:
        model = SecurityZoneMatrixPolicy
        fields = ("id", "name", "action", "color", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = Q(name__icontains=value) | Q(description__icontains=value)
        return queryset.filter(qs_filter)
