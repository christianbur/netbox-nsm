import django_filters
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from netbox.filtersets import NetBoxModelFilterSet
from utilities.filters import MultiValueCharFilter
from utilities.filtersets import register_filterset

from netbox_nsm.models import CotRulebookAssignment

__all__ = ("CotRulebookAssignmentFilterSet",)


@register_filterset
class CotRulebookAssignmentFilterSet(NetBoxModelFilterSet):
    cot_slug = MultiValueCharFilter(field_name="cot_slug", label=_("Rulebook slug"))

    class Meta:
        model = CotRulebookAssignment
        fields = ("id", "cot_slug", "assigned_object_type", "assigned_object_id")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(cot_slug__icontains=value) | Q(description__icontains=value)
        )
