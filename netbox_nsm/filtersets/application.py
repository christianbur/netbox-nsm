import django_filters
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from netbox.filtersets import PrimaryModelFilterSet
from tenancy.filtersets import TenancyFilterSet
from utilities.filtersets import register_filterset
from utilities.filters import (
    MultiValueCharFilter,
    MultiValueNumberFilter,
)

from dcim.models import Device, VirtualDeviceContext
from virtualization.models import VirtualMachine

from netbox_nsm.models import (
    Application,
    ApplicationSet,
    ApplicationItem,
)


__all__ = (
    "ApplicationFilterSet",
)


@register_filterset
class ApplicationFilterSet(TenancyFilterSet, PrimaryModelFilterSet):
    application_items_id = django_filters.ModelMultipleChoiceFilter(
        field_name="application_items",
        queryset=ApplicationItem.objects.all(),
        to_field_name="id",
        label=_("Application Item (ID)"),
    )
    application_items = django_filters.ModelMultipleChoiceFilter(
        field_name="application_items__name",
        queryset=ApplicationItem.objects.all(),
        to_field_name="name",
        label=_("Application Item (name)"),
    )
    category = MultiValueCharFilter(field_name="category", label=_("Category"))
    subcategory = MultiValueCharFilter(
        field_name="subcategory", label=_("Subcategory")
    )
    technology = MultiValueCharFilter(field_name="technology", label=_("Technology"))
    reference = MultiValueCharFilter(field_name="reference", label=_("Reference"))
    application_item_id = django_filters.ModelMultipleChoiceFilter(
        field_name="application_items",
        queryset=ApplicationItem.objects.all(),
        to_field_name="id",
        label=_("Application (ID)"),
    )
    application_set_id = django_filters.ModelMultipleChoiceFilter(
        queryset=ApplicationSet.objects.all(),
        field_name="applicationset_applications",
        to_field_name="id",
        label=_("Application Set (ID)"),
    )

    class Meta:
        model = Application
        fields = [
            "id",
            "name",
            "description",
            "identifier",
            "category",
            "subcategory",
            "standard_ports_text",
            "technology",
            "reference",
        ]

    def search(self, queryset, name, value):
        """Perform the filtered search."""
        if not value.strip():
            return queryset
        qs_filter = (
            Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(identifier__icontains=value)
            | Q(category__icontains=value)
            | Q(subcategory__icontains=value)
            | Q(standard_ports_text__icontains=value)
            | Q(technology__icontains=value)
            | Q(reference__icontains=value)
        )
        return queryset.filter(qs_filter)


@register_filterset
