from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import View

from netbox.views import generic
from utilities.views import register_model_view

from netbox_nsm.builtin_types import BUILTIN_CUSTOM_TYPES
from netbox_nsm.filtersets import SecurityObjectTypeFilterSet
from netbox_nsm.forms import (
    SecurityObjectTypeBulkEditForm,
    SecurityObjectTypeFilterForm,
    SecurityObjectTypeForm,
    SecurityObjectTypeImportForm,
)
from netbox_nsm.models import SecurityObjectType, SecurityArea, SecurityObject
from netbox_nsm.tables import SecurityObjectTypeTable


@register_model_view(SecurityObjectType)
class SecurityObjectTypeView(generic.ObjectView):
    queryset = SecurityObjectType.objects.all()
    template_name = "netbox_nsm/securityobjecttype.html"


@register_model_view(SecurityObjectType, "list", path="", detail=False)
class SecurityObjectTypeListView(generic.ObjectListView):
    queryset = SecurityObjectType.objects.all()
    filterset = SecurityObjectTypeFilterSet
    filterset_form = SecurityObjectTypeFilterForm
    table = SecurityObjectTypeTable


@register_model_view(SecurityObjectType, "add", detail=False)
@register_model_view(SecurityObjectType, "edit")
class SecurityObjectTypeEditView(generic.ObjectEditView):
    queryset = SecurityObjectType.objects.all()
    form = SecurityObjectTypeForm


@register_model_view(SecurityObjectType, "delete")
class SecurityObjectTypeDeleteView(generic.ObjectDeleteView):
    queryset = SecurityObjectType.objects.all()


@register_model_view(SecurityObjectType, "bulk_edit", path="edit", detail=False)
class SecurityObjectTypeBulkEditView(generic.BulkEditView):
    queryset = SecurityObjectType.objects.all()
    filterset = SecurityObjectTypeFilterSet
    table = SecurityObjectTypeTable
    form = SecurityObjectTypeBulkEditForm


@register_model_view(SecurityObjectType, "bulk_delete", path="delete", detail=False)
class SecurityObjectTypeBulkDeleteView(generic.BulkDeleteView):
    queryset = SecurityObjectType.objects.all()
    table = SecurityObjectTypeTable


@register_model_view(SecurityObjectType, "bulk_import", detail=False)
class SecurityObjectTypeBulkImportView(generic.BulkImportView):
    queryset = SecurityObjectType.objects.all()
    model_form = SecurityObjectTypeImportForm


class BuiltinTypeInstallView(LoginRequiredMixin, View):
    """Show all built-in type definitions and let the admin install selected ones."""

    def get(self, request):
        import json
        from django.shortcuts import render

        installed_names = set(SecurityObjectType.objects.values_list("name", flat=True))

        enriched = []
        for t in BUILTIN_CUSTOM_TYPES:
            fds_display = [fd for fd in t.get("field_definitions", []) if not fd.get("__meta__")]
            enriched.append({
                **t,
                "already_installed": t["name"] in installed_names,
                "field_definitions_json": json.dumps(fds_display, ensure_ascii=False, indent=2),
            })

        return render(request, "netbox_nsm/builtin_type_install.html", {
            "builtin_types": enriched,
        })

    def post(self, request):
        if not request.user.has_perm("netbox_nsm.add_securityobjecttype"):
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
            if SecurityObjectType.objects.filter(name=custom_name).exists():
                messages.warning(request, f"'{custom_name}' already exists — skipped.")
                continue
            area_slug = t["area"]
            area_obj = SecurityArea.objects.filter(slug=area_slug).first()
            if not area_obj:
                messages.warning(request, f"Area '{area_slug}' not found — skipped '{custom_name}'.")
                continue
            obj_type = SecurityObjectType.objects.create(
                name=custom_name,
                area=area_obj,
                description=t.get("description", ""),
                field_definitions=t.get("field_definitions", []),
                display_template=t.get("display_template", ""),
            )
            for default_obj in t.get("default_objects", []):
                SecurityObject.objects.get_or_create(
                    name=default_obj["name"],
                    custom_type=obj_type,
                    defaults={"field_data": default_obj.get("field_data", {})},
                )
            created += 1

        if created:
            messages.success(request, f"{created} type(s) installed successfully.")
        elif not selected_indices:
            messages.info(request, "No types selected.")
        return redirect("/plugins/netbox-nsm/object/custom/types/")
