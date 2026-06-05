"""NSM setup wizard view."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View

from ipam.models import IPAddress

from netbox_nsm.setup_flags import setup_allow_destructive_actions, setup_menu_enabled

from . import custom_objects, demo, typeconfig

__all__ = ("SetupView",)


class SetupView(LoginRequiredMixin, View):
    template_name = "netbox_nsm/setup.html"

    def dispatch(self, request, *args, **kwargs):
        if not setup_menu_enabled():
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        co_loaded = custom_objects.custom_objects_plugin_loaded()
        co_ready = custom_objects.custom_objects_db_ready()
        cot_status = custom_objects.get_cot_status() if co_loaded else None
        tc_status = typeconfig.get_typeconfig_status() if co_ready else None
        cots_ok = custom_objects.all_cots_ok(cot_status) if cot_status else False
        tcs_ok = (
            typeconfig.all_typeconfigs_ok(cot_status, tc_status)
            if cot_status and tc_status
            else False
        )

        return render(
            request,
            self.template_name,
            {
                "custom_objects_plugin_loaded": co_loaded,
                "custom_objects_db_ready": co_ready,
                "plugin_installed": co_ready,
                "cot_status": cot_status,
                "tc_status": tc_status,
                "all_cots_ok": cots_ok,
                "all_tcs_ok": tcs_ok,
                "enterprise_demo_blocked": IPAddress.objects.exists(),
                "setup_allow_destructive_actions": setup_allow_destructive_actions(),
            },
        )

    def post(self, request):
        action = request.POST.get("action", "")

        if action and not custom_objects.custom_objects_db_ready():
            messages.error(
                request,
                _(
                    "netbox-custom-objects database tables are missing. "
                    "Run: python manage.py migrate netbox_custom_objects"
                ),
            )
            return redirect(reverse("plugins:netbox_nsm:setup"))

        if demo.handles_action(action) and not setup_allow_destructive_actions():
            messages.error(
                request,
                _("Demo actions are disabled (setup_allow_destructive_actions)."),
            )
            return redirect(reverse("plugins:netbox_nsm:setup"))

        try:
            if custom_objects.handles_action(action):
                return custom_objects.handle_custom_objects_action(request, action)
            if typeconfig.handles_action(action):
                return typeconfig.handle_typeconfig_action(request, action)
            if demo.handles_action(action):
                return demo.handle_demo_action(request, action)
        except Exception as exc:
            messages.error(request, _("Error: %(error)s") % {"error": exc})

        return redirect(reverse("plugins:netbox_nsm:setup"))
