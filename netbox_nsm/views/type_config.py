from django.urls import reverse

from netbox.views import generic
from utilities.views import register_model_view

from netbox_nsm.forms.type_config import TypeConfigAddForm, TypeConfigForm
from netbox_nsm.models import TypeConfig
from netbox_nsm.tables.type_config import TypeConfigTable

__all__ = (
    "TypeConfigListView",
    "TypeConfigAddView",
    "TypeConfigEditView",
    "TypeConfigDeleteView",
)


class TypeConfigListView(generic.ObjectListView):
    queryset = TypeConfig.objects.select_related("content_type")
    table = TypeConfigTable

    def get_extra_context(self, request):
        return {
            "add_url": reverse("plugins:netbox_nsm:typeconfig_add"),
        }


class TypeConfigAddView(generic.ObjectEditView):
    queryset = TypeConfig.objects.select_related("content_type")
    form = TypeConfigAddForm

    def get_return_url(self, request, obj=None):
        return reverse("plugins:netbox_nsm:typeconfig_list")


@register_model_view(TypeConfig, "edit")
class TypeConfigEditView(generic.ObjectEditView):
    queryset = TypeConfig.objects.select_related("content_type")
    form = TypeConfigForm

    def get_return_url(self, request, obj=None):
        return reverse("plugins:netbox_nsm:typeconfig_list")


@register_model_view(TypeConfig, "delete")
class TypeConfigDeleteView(generic.ObjectDeleteView):
    queryset = TypeConfig.objects.select_related("content_type")

    def get_return_url(self, request, obj=None):
        return reverse("plugins:netbox_nsm:typeconfig_list")
