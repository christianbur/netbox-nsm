"""NSM setup wizard view."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View

from ipam.models import IPAddress

from netbox_nsm.core.setup_flags import setup_allow_destructive_actions, setup_menu_enabled
from netbox_nsm.demos.addresses_million_scale import (
    SCALE_DEMO_50K_LEAF_COUNT,
    SCALE_DEMO_50K_RULE_COUNT,
)
from netbox_nsm.objects.nsm_config_permissions import (
    ADD_CUSTOM_OBJECT_TYPE,
    CHANGE_CUSTOM_OBJECT_TYPE,
    VIEW_CUSTOM_OBJECT_TYPE,
)

from . import custom_objects, demo, typeconfig

__all__ = ("SetupView",)


class SetupView(LoginRequiredMixin, View):
    template_name = "netbox_nsm/setup.html"

    def dispatch(self, request, *args, **kwargs):
        if not setup_menu_enabled():
            raise Http404
        if not request.user.has_perm(VIEW_CUSTOM_OBJECT_TYPE):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

    def _build_context(self):
        co_loaded = custom_objects.custom_objects_plugin_loaded()
        co_ready = custom_objects.custom_objects_db_ready()
        cot_status = (
            custom_objects.get_cot_status()
            if co_loaded
            else custom_objects.empty_cot_status()
        )
        rulebook_template_status = (
            custom_objects.get_rulebook_template_status()
            if co_ready
            else custom_objects.empty_rulebook_template_status()
        )
        tc_status = (
            typeconfig.get_typeconfig_status()
            if co_ready
            else typeconfig.empty_typeconfig_status()
        )
        cots_ok = (
            custom_objects.all_cots_ok(cot_status, rulebook_template_status)
            if co_loaded
            else False
        )
        tcs_ok = (
            typeconfig.all_typeconfigs_ok(cot_status, tc_status) if co_ready else False
        )
        section2_ok = cots_ok and tcs_ok
        ipam_has_ip_addresses = IPAddress.objects.exists()
        from netbox_nsm.objects.type_config_export import (
            format_all_type_configs_comment_yaml,
        )

        return {
            "custom_objects_plugin_loaded": co_loaded,
            "custom_objects_db_ready": co_ready,
            "cot_status": cot_status,
            "cot_setup_groups": custom_objects.get_cot_setup_groups(
                cot_status=cot_status,
                rulebook_template_status=rulebook_template_status,
            ),
            "cot_schema_yaml": custom_objects.get_cot_schema_yaml(),
            "cot_schema_preview": custom_objects.get_cot_schema_preview(),
            "tc_status": tc_status,
            "all_cots_ok": cots_ok,
            "all_tcs_ok": tcs_ok,
            "can_create_typeconfigs": cots_ok and not tcs_ok,
            "typeconfigs_definition_yaml": format_all_type_configs_comment_yaml(),
            "can_import_cots": co_ready and not section2_ok,
            "can_run_demo": section2_ok and setup_allow_destructive_actions(),
            "can_run_scale_demo_50k": (
                section2_ok and setup_allow_destructive_actions()
            ),
            "starter_demo_zone_count": demo.DEMO_ZONE_COUNT,
            "starter_demo_rule_count": demo.DEMO_RULE_COUNT,
            "starter_demo_grid_size": demo.DEMO_GRID_SIZE,
            "scale_demo_50k_leaf_count": SCALE_DEMO_50K_LEAF_COUNT,
            "scale_demo_50k_rule_count": SCALE_DEMO_50K_RULE_COUNT,
            "ipam_has_ip_addresses": ipam_has_ip_addresses,
            "setup_allow_destructive_actions": setup_allow_destructive_actions(),
        }

    def get(self, request):
        return render(request, self.template_name, self._build_context())

    def post(self, request):
        action = request.POST.get("action", "")

        if custom_objects.handles_action(action) and not request.user.has_perm(
            ADD_CUSTOM_OBJECT_TYPE
        ):
            messages.error(
                request,
                _("Permission denied: %(perm)s") % {"perm": ADD_CUSTOM_OBJECT_TYPE},
            )
            return redirect(reverse("plugins:netbox_nsm:setup"))

        if typeconfig.handles_action(action) and not request.user.has_perm(
            CHANGE_CUSTOM_OBJECT_TYPE
        ):
            messages.error(
                request,
                _("Permission denied: %(perm)s") % {"perm": CHANGE_CUSTOM_OBJECT_TYPE},
            )
            return redirect(reverse("plugins:netbox_nsm:setup"))

        if action and not custom_objects.custom_objects_db_ready():
            messages.error(
                request,
                _(
                    "netbox-custom-objects database tables are missing. "
                    "Run: python manage.py migrate netbox_custom_objects"
                ),
            )
            return redirect(reverse("plugins:netbox_nsm:setup"))

        ctx = self._build_context()

        if custom_objects.handles_action(action) and not ctx["can_import_cots"]:
            if not ctx["custom_objects_db_ready"]:
                messages.error(
                    request,
                    _(
                        "netbox-custom-objects is not ready. Install the plugin "
                        "and run migrations first."
                    ),
                )
            elif ctx["all_cots_ok"] and ctx["all_tcs_ok"]:
                messages.info(
                    request,
                    _("All Custom Object Types and Object Configs are already present."),
                )
            return redirect(reverse("plugins:netbox_nsm:setup"))

        if typeconfig.handles_action(action) and not ctx["can_create_typeconfigs"]:
            if not ctx["all_cots_ok"]:
                messages.error(
                    request,
                    _("Complete section 2 (Custom Object Types) first."),
                )
            elif ctx["all_tcs_ok"]:
                messages.info(
                    request,
                    _("All Object Configs are already present."),
                )
            return redirect(reverse("plugins:netbox_nsm:setup"))

        if demo.handles_action(action):
            if not setup_allow_destructive_actions():
                messages.error(
                    request,
                    _("Demo actions are disabled (setup_allow_destructive_actions)."),
                )
                return redirect(reverse("plugins:netbox_nsm:setup"))
            if not (ctx["all_cots_ok"] and ctx["all_tcs_ok"]):
                messages.error(
                    request,
                    _("Complete section 2 (Custom Object Schema) before running demos."),
                )
                return redirect(reverse("plugins:netbox_nsm:setup"))
            if action == "create_demo_enterprise" and IPAddress.objects.exists():
                messages.error(
                    request,
                    _("Enterprise demo requires an empty IP address database."),
                )
                return redirect(reverse("plugins:netbox_nsm:setup"))
            if action == "create_demo_scale_50k" and not request.POST.get(
                "scale_demo_50k_confirm"
            ):
                messages.error(
                    request,
                    _(
                        "Please confirm that IP addresses may be created "
                        "before starting the address bench."
                    ),
                )
                return redirect(reverse("plugins:netbox_nsm:setup"))

        try:
            if custom_objects.handles_action(action):
                return custom_objects.handle_custom_objects_action(request, action)
            if typeconfig.handles_action(action):
                return typeconfig.handle_typeconfig_action(request, action)
            if demo.handles_action(action):
                return demo.handle_demo_action(request, action)
            if action:
                messages.warning(
                    request, _("Unknown action: %(action)s") % {"action": action}
                )
        except Exception as exc:
            messages.error(request, _("Error: %(error)s") % {"error": exc})

        return redirect(reverse("plugins:netbox_nsm:setup"))
