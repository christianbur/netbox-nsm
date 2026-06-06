from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.views import generic
from utilities.views import register_model_view

from netbox_nsm.filtersets import TypeConfigFilterSet
from netbox_nsm.forms import TypeConfigAddForm, TypeConfigForm
from netbox_nsm.models import TypeConfig
from netbox_nsm.tables import TypeConfigTable

__all__ = (
    "TypeConfigView",
    "TypeConfigListView",
    "TypeConfigAddView",
    "TypeConfigEditView",
    "TypeConfigDeleteView",
)


@register_model_view(TypeConfig)
class TypeConfigView(generic.ObjectView):
    queryset = TypeConfig.objects.select_related("content_type")


@register_model_view(TypeConfig, "list", path="", detail=False)
class TypeConfigListView(generic.ObjectListView):
    queryset = TypeConfig.objects.select_related("content_type")
    table = TypeConfigTable
    filterset = TypeConfigFilterSet


@register_model_view(TypeConfig, "add", detail=False)
class TypeConfigAddView(generic.ObjectEditView):
    queryset = TypeConfig.objects.all()
    form = TypeConfigAddForm

    def get_return_url(self, request, obj=None):
        if obj and obj.pk:
            return obj.get_absolute_url()
        return reverse("plugins:netbox_nsm:typeconfig_list")


@register_model_view(TypeConfig, "edit")
class TypeConfigEditView(generic.ObjectEditView):
    queryset = TypeConfig.objects.select_related("content_type")
    form = TypeConfigForm

    def get_return_url(self, request, obj=None):
        if obj and obj.pk:
            return obj.get_absolute_url()
        return reverse("plugins:netbox_nsm:typeconfig_list")


@register_model_view(TypeConfig, "delete")
class TypeConfigDeleteView(generic.ObjectDeleteView):
    queryset = TypeConfig.objects.all()

    def get_return_url(self, request, obj=None):
        return reverse("plugins:netbox_nsm:typeconfig_list")
