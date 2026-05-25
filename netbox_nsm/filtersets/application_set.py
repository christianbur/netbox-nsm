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
    ApplicationSet,
    Application,
)


__all__ = (
    "ApplicationSetFilterSet",
)


@register_filterset
class ApplicationSetFilterSet(TenancyFilterSet, PrimaryModelFilterSet):
    applications_id = django_filters.ModelMultipleChoiceFilter(
        field_name="applications",
        queryset=Application.objects.all(),
        to_field_name="id",
        label=_("Application (ID)"),
    )
    applications = django_filters.ModelMultipleChoiceFilter(
        field_name="applications__name",
        queryset=Application.objects.all(),
        to_field_name="name",
        label=_("Application (name)"),
    )
    application_sets_id = django_filters.ModelMultipleChoiceFilter(
        field_name="application_sets",
        queryset=ApplicationSet.objects.all(),
        to_field_name="id",
        label=_("Application Set (name)"),
    )
    application_sets = django_filters.ModelMultipleChoiceFilter(
        field_name="application_sets__name",
        queryset=ApplicationSet.objects.all(),
        to_field_name="name",
        label=_("Application Set (name)"),
    )
    application_id = django_filters.ModelMultipleChoiceFilter(
        field_name="applications",
        queryset=Application.objects.all(),
        to_field_name="id",
        label=_("Application (ID)"),
    )
    application_set_id = django_filters.ModelMultipleChoiceFilter(
        field_name="application_sets",
        queryset=ApplicationSet.objects.all(),
        to_field_name="id",
        label=_("Application Set (ID)"),
    )

    class Meta:
        model = ApplicationSet
        fields = ["id", "name", "description", "identifier"]

    def search(self, queryset, name, value):
        """Perform the filtered search."""
        if not value.strip():
            return queryset
        qs_filter = (
            Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(identifier__icontains=value)
        )
        return queryset.filter(qs_filter)


@register_filterset
