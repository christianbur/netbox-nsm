from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import View

from netbox.views import generic
from utilities.views import register_model_view

from netbox_nsm.builtin_types import BUILTIN_CUSTOM_TYPES
from netbox_nsm.filtersets import ObjectCustomTypeFilterSet
from netbox_nsm.forms import (
    ObjectCustomTypeBulkEditForm,
    ObjectCustomTypeFilterForm,
    ObjectCustomTypeForm,
    ObjectCustomTypeImportForm,
)
from netbox_nsm.models import ObjectCustomType
from netbox_nsm.tables import ObjectCustomTypeTable


@register_model_view(ObjectCustomType)
class ObjectCustomTypeView(generic.ObjectView):
    queryset = ObjectCustomType.objects.all()
    template_name = "netbox_nsm/objectcustomtype.html"


@register_model_view(ObjectCustomType, "list", path="", detail=False)
class ObjectCustomTypeListView(generic.ObjectListView):
    queryset = ObjectCustomType.objects.all()
    filterset = ObjectCustomTypeFilterSet
    filterset_form = ObjectCustomTypeFilterForm
    table = ObjectCustomTypeTable


@register_model_view(ObjectCustomType, "add", detail=False)
@register_model_view(ObjectCustomType, "edit")
class ObjectCustomTypeEditView(generic.ObjectEditView):
    queryset = ObjectCustomType.objects.all()
    form = ObjectCustomTypeForm


@register_model_view(ObjectCustomType, "delete")
class ObjectCustomTypeDeleteView(generic.ObjectDeleteView):
    queryset = ObjectCustomType.objects.all()


@register_model_view(ObjectCustomType, "bulk_edit", path="edit", detail=False)
class ObjectCustomTypeBulkEditView(generic.BulkEditView):
    queryset = ObjectCustomType.objects.all()
    filterset = ObjectCustomTypeFilterSet
    table = ObjectCustomTypeTable
    form = ObjectCustomTypeBulkEditForm


@register_model_view(ObjectCustomType, "bulk_delete", path="delete", detail=False)
class ObjectCustomTypeBulkDeleteView(generic.BulkDeleteView):
    queryset = ObjectCustomType.objects.all()
    table = ObjectCustomTypeTable


@register_model_view(ObjectCustomType, "bulk_import", detail=False)
class ObjectCustomTypeBulkImportView(generic.BulkImportView):
    queryset = ObjectCustomType.objects.all()
    model_form = ObjectCustomTypeImportForm


class BuiltinTypeInstallView(LoginRequiredMixin, View):
    """Show all built-in type definitions and let the admin install selected ones."""

    def get(self, request):
        from django.shortcuts import render
        return render(request, "netbox_nsm/builtin_type_install.html", {
            "builtin_types": BUILTIN_CUSTOM_TYPES,
        })

    def post(self, request):
        if not request.user.has_perm("netbox_nsm.add_objectcustomtype"):
            messages.error(request, "Permission denied to create Custom Types.")
            return redirect("/plugins/netbox-nsm/object/custom/types/")

        selected_indices = request.POST.getlist("selected")
        created = 0
        for idx_str in selected_indices:
            try:
                t = BUILTIN_CUSTOM_TYPES[int(idx_str)]
            except (ValueError, IndexError):
                continue
            custom_name = request.POST.get(f"name_{idx_str}", t["name"]).strip()
            if not custom_name:
                continue
            if ObjectCustomType.objects.filter(name=custom_name).exists():
                messages.warning(request, f"'{custom_name}' already exists — skipped.")
                continue
            ObjectCustomType.objects.create(
                name=custom_name,
                area=t["area"],
                icon=t.get("icon", ""),
                description=t.get("description", ""),
                field_definitions=t.get("field_definitions", []),
            )
            created += 1

        if created:
            messages.success(request, f"{created} type(s) installed successfully.")
        elif not selected_indices:
            messages.info(request, "No types selected.")
        return redirect("/plugins/netbox-nsm/object/custom/types/")
