import django_filters
from django.db.models import Q

from netbox.filtersets import PrimaryModelFilterSet

from netbox_nsm.models import ObjectGroup
from netbox_nsm.panel_sections import get_panel_section_choices

__all__ = ("ObjectGroupFilterSet",)


class ObjectGroupFilterSet(PrimaryModelFilterSet):
    field_slug = django_filters.MultipleChoiceFilter(
        choices=get_panel_section_choices,
        method="filter_field_slugs",
    )

    class Meta:
        model = ObjectGroup
        fields = ("id", "name", "field_slug")

    def filter_field_slugs(self, queryset, name, value):
        if not value:
            return queryset
        q = Q()
        for slug in value:
            q |= Q(field_slugs__contains=[slug])
        return queryset.filter(q).distinct()
