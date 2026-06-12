"""AJAX validation for setup Custom Object Schema YAML."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

from netbox_nsm.objects.custom_objects_schema import validate_custom_objects_schema_yaml

__all__ = ("SetupSchemaValidateView",)


class SetupSchemaValidateView(LoginRequiredMixin, View):
    def post(self, request):
        yaml_text = request.POST.get("schema_yaml", "")
        try:
            validate_custom_objects_schema_yaml(yaml_text)
        except Exception as exc:
            return JsonResponse({"valid": False, "error": str(exc)}, status=400)
        return JsonResponse({"valid": True})
