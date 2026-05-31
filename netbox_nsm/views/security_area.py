from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect

from netbox.views import generic
from utilities.views import register_model_view

from netbox_nsm.filtersets import SecurityAreaFilterSet
from netbox_nsm.forms import SecurityAreaForm, SecurityAreaFilterForm
from netbox_nsm.models import SecurityArea
from netbox_nsm.tables import SecurityAreaTable

__all__ = (
    "SecurityAreaView",
    "SecurityAreaListView",
    "SecurityAreaEditView",
    "SecurityAreaDeleteView",
)


@register_model_view(SecurityArea)
class SecurityAreaView(generic.ObjectView):
    queryset = SecurityArea.objects.prefetch_related("tags")
    template_name = "netbox_nsm/securityarea.html"

    def get_extra_context(self, request, instance):
        return {
            "type_count": instance.object_types.count(),
            "group_count": instance.object_groups.count(),
        }


@register_model_view(SecurityArea, "list", path="", detail=False)
class SecurityAreaListView(generic.ObjectListView):
    queryset = SecurityArea.objects.all()
    filterset = SecurityAreaFilterSet
    filterset_form = SecurityAreaFilterForm
    table = SecurityAreaTable


@register_model_view(SecurityArea, "add", detail=False)
@register_model_view(SecurityArea, "edit")
class SecurityAreaEditView(generic.ObjectEditView):
    queryset = SecurityArea.objects.all()
    form = SecurityAreaForm


@register_model_view(SecurityArea, "delete")
class SecurityAreaDeleteView(generic.ObjectDeleteView):
    queryset = SecurityArea.objects.all()

    def post(self, request, *args, **kwargs):
        from django.core.exceptions import ValidationError

        obj_id = kwargs.get("pk") or kwargs.get("id")
        if obj_id is None:
            raise Http404("Missing object identifier")
        try:
            obj = SecurityArea.objects.get(pk=obj_id)
        except SecurityArea.DoesNotExist:
            raise Http404("Area not found")
        try:
            obj.delete()
        except ValidationError as e:
            messages.error(request, str(e.message))
            return redirect(obj.get_absolute_url())
        messages.success(request, f"Area '{obj}' deleted.")
        return redirect("plugins:netbox_nsm:securityarea_list")
