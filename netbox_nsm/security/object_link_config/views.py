"""Views for Object Link schema configuration."""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View

from netbox_nsm.security.object_link_config.forms import ObjectLinkConfigForm
from netbox_nsm.security.object_link_config.service import (
    apply_object_link_schema_changes,
    get_object_link_config_state,
    prepare_object_link_type_panels,
    preview_object_link_schema_changes,
)
from netbox_nsm.type_metadata.permissions import (
    CHANGE_CUSTOM_OBJECT_TYPE,
    VIEW_CUSTOM_OBJECT_TYPE,
)

__all__ = (
    "ObjectLinkConfigApplyView",
    "ObjectLinkConfigEditView",
    "ObjectLinkConfigPreviewView",
    "ObjectLinkConfigView",
)


class _ObjectLinkConfigBase(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm(VIEW_CUSTOM_OBJECT_TYPE):
            raise PermissionDenied
        if get_object_link_config_state() is None:
            raise Http404(_("Object Link COT is not deployed. Apply the NSM Schema bundle first."))
        return super().dispatch(request, *args, **kwargs)


class ObjectLinkConfigView(_ObjectLinkConfigBase):
    template_name = "netbox_nsm/object_link_config.html"

    def get(self, request):
        state = get_object_link_config_state()
        host_types, security_types = prepare_object_link_type_panels(state)
        return render(
            request,
            self.template_name,
            {
                "state": state,
                "host_types": host_types,
                "security_types": security_types,
                "edit_url": reverse("plugins:netbox_nsm:object_link_config_edit"),
            },
        )


class ObjectLinkConfigEditView(_ObjectLinkConfigBase):
    template_name = "netbox_nsm/object_link_config_edit.html"

    def _edit_context(self, request, *, state):
        host_types, security_types = prepare_object_link_type_panels(state)
        return {
            "state": state,
            "host_types": host_types,
            "security_types": security_types,
            "preview_url": reverse("plugins:netbox_nsm:object_link_config_preview"),
            "apply_url": reverse("plugins:netbox_nsm:object_link_config_apply"),
            "back_url": reverse("plugins:netbox_nsm:object_link_config"),
            "can_change": request.user.has_perm(CHANGE_CUSTOM_OBJECT_TYPE),
        }

    def get(self, request):
        state = get_object_link_config_state()
        return render(
            request,
            self.template_name,
            self._edit_context(request, state=state),
        )


class ObjectLinkConfigPreviewView(_ObjectLinkConfigBase):
    def post(self, request):
        form = ObjectLinkConfigForm(request.POST)
        if not form.is_valid():
            return JsonResponse({"errors": form.errors}, status=400)
        try:
            preview = preview_object_link_schema_changes(
                form.cleaned_data["host_types"],
                form.cleaned_data["security_types"],
            )
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        return JsonResponse(preview)


class ObjectLinkConfigApplyView(_ObjectLinkConfigBase):
    def post(self, request):
        if not request.user.has_perm(CHANGE_CUSTOM_OBJECT_TYPE):
            raise PermissionDenied
        form = ObjectLinkConfigForm(request.POST)
        if not form.is_valid():
            return JsonResponse({"errors": form.errors}, status=400)
        try:
            preview = apply_object_link_schema_changes(
                form.cleaned_data["host_types"],
                form.cleaned_data["security_types"],
                allow_destructive=form.cleaned_data.get("allow_destructive", False),
            )
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        return JsonResponse({"ok": True, "preview": preview})
