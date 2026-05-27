"""
Views for YAML Bundle export and import.

Export:  GET /object/bundle/export/?type=<pk>[&type=<pk>...]
         → downloads a .yaml file containing the selected CustomType(s)
           and all their CustomObjects.
         If no ?type= is given, all CustomTypes + objects are exported.

Import:  GET  /object/bundle/import/ → shows textarea form
         POST /object/bundle/import/ → parses YAML and creates/updates objects
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views import View

from netbox_nsm.models import SecurityObject, SecurityObjectType
from netbox_nsm.serializers.yaml_bundle import (
    build_bundle_yaml,
    export_custom_object,
    export_custom_type,
    import_bundle,
    parse_bundle,
)


class NSMExportYAMLView(LoginRequiredMixin, View):
    """Return a YAML bundle file as a download."""

    def get(self, request):
        pk_list = request.GET.getlist("type")

        if pk_list:
            types = SecurityObjectType.objects.filter(pk__in=pk_list)
        else:
            types = SecurityObjectType.objects.all().order_by("area", "name")

        items = []
        for ct in types:
            items.append(export_custom_type(ct))
            for obj in ct.custom_objects.order_by("name"):
                items.append(export_custom_object(obj))

        description = request.GET.get("description", "")
        yaml_text = build_bundle_yaml(items, description=description)

        response = HttpResponse(yaml_text, content_type="text/yaml; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="nsm-bundle.yaml"'
        return response


class NSMImportYAMLView(LoginRequiredMixin, View):
    """Show an import form (GET) and process pasted/uploaded YAML (POST)."""

    template_name = "netbox_nsm/yaml_bundle_import.html"

    def get(self, request):
        return render(request, self.template_name, {})

    def post(self, request):
        # Accept YAML from textarea or uploaded file
        yaml_text = ""
        uploaded = request.FILES.get("yaml_file")
        if uploaded:
            try:
                yaml_text = uploaded.read().decode("utf-8")
            except Exception as exc:
                messages.error(request, f"Cannot read uploaded file: {exc}")
                return render(request, self.template_name, {})
        else:
            yaml_text = request.POST.get("yaml_text", "").strip()

        if not yaml_text:
            messages.error(request, "No YAML provided.")
            return render(request, self.template_name, {"yaml_text": yaml_text})

        update_existing = request.POST.get("update_existing") == "1"

        try:
            items = parse_bundle(yaml_text)
        except ValueError as exc:
            messages.error(request, f"Parse error: {exc}")
            return render(request, self.template_name, {"yaml_text": yaml_text})

        created, updated, errors = import_bundle(items, update_existing=update_existing)

        for msg in created:
            messages.success(request, f"Created: {msg}")
        for msg in updated:
            messages.info(request, f"Updated: {msg}")
        for msg in errors:
            messages.warning(request, msg)

        if not created and not updated and not errors:
            messages.info(request, "Bundle contained no importable items.")

        return redirect(request.path)
