from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404

from netbox.views import generic
from utilities.views import register_model_view

from netbox_nsm.models import AddressList
from netbox_nsm.filtersets import (
    AddressListFilterSet,
)
from netbox_nsm.tables import (
    AddressListTable,
)
from netbox_nsm.forms import (
    AddressListForm,
    AddressListFilterForm,
)

__all__ = (
    "AddressListEditView",
    "AddressListDeleteView",
)


@register_model_view(AddressList, "list", path="", detail=False)
class AddressListView(generic.ObjectListView):
    queryset = AddressList.objects.all()
    filterset = AddressListFilterSet
    filterset_form = AddressListFilterForm
    table = AddressListTable
    actions = ()


@register_model_view(AddressList, "add", detail=False)
@register_model_view(AddressList, "edit")
class AddressListEditView(generic.ObjectEditView):
    queryset = AddressList.objects.all()
    form = AddressListForm

    def alter_object(self, instance, request, args, kwargs):
        if not instance.pk:
            content_type = get_object_or_404(
                ContentType, pk=request.GET.get("assigned_object_type")
            )
            instance.assigned_object = get_object_or_404(
                content_type.model_class(), pk=request.GET.get("assigned_object_id")
            )
        return instance

    def get_extra_addanother_params(self, request):
        return {
            "assigned_object_type": request.GET.get("assigned_object_type"),
            "assigned_object_id": request.GET.get("assigned_object_id"),
        }


@register_model_view(AddressList, "delete")
class AddressListDeleteView(generic.ObjectDeleteView):
    queryset = AddressList.objects.all()
