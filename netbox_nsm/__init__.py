from django.utils.translation import gettext_lazy as _
from netbox.plugins import PluginConfig
from .version import __version__


class SecurityConfig(PluginConfig):
    name = "netbox_nsm"
    verbose_name = _("NetBox NSM - Network Security Management")
    description = _(
        "Document network security policy in NetBox: rulebooks, zones, NSM links, "
        "and the Security tab (requires netbox-custom-objects)."
    )
    version = __version__
    author = "Christian Burmeister"
    author_email = ""
    base_url = "netbox-nsm"
    required_settings = []
    min_version = "4.5.0"
    max_version = "4.6.99"
    default_settings = {
        # Show top-level NSM menu (default: on)
        "top_level_menu": True,
        # Show Security → Configuration → Bundles and allow /bundles/ URLs (default: on)
        "bundles_menu": True,
        # Legacy alias for bundles_menu (still supported)
        "setup_menu": True,
        # Bundles: destructive preview/apply checkbox and demo bundle actions (default: on)
        "setup_allow_destructive_actions": True,
        # Top-level menu and Security tab title (default: "Security")
        "menu_label": "",
        "panel_label": "",
        # Optional Jinja2 naming for nsm_address / nsm_address_group (see docs/address_name_templates.md)
        "address_name_templates": [],
        "address_group_name_templates": [],
        # Extra bundle directories; same slug overrides built-in bundles
        "bundle_paths": [],
        # Include built-in bundles shipped with the plugin (default: True)
        "builtin_bundles": True,
    }

    def ready(self):
        super().ready()
        from netbox_nsm.core.branching_support import register_branching_models
        from netbox_nsm.security.tab import register_security_tabs

        register_branching_models()
        register_security_tabs()
        from netbox_nsm.objects.cot_routes import (
            apply_nsm_object_co_view_patches,
            apply_nsm_object_url_patches,
        )

        apply_nsm_object_url_patches()
        apply_nsm_object_co_view_patches()
        self._warm_url_resolver()
        self._register_system_jobs()
        self._patch_color_field_widget()
        self._patch_poly_subfield_labels()
        self._patch_cot_rule_add_index()
        self._patch_custom_object_list_polymorphic_sort()

    @staticmethod
    def _warm_url_resolver():
        """Populate Django's URL resolver at startup (avoids ~2s first-request penalty)."""
        try:
            from django.urls import reverse

            reverse("plugins:netbox_nsm:rulebook_list")
        except Exception:
            pass

    @staticmethod
    def _register_system_jobs():
        """Import the object report job module so ``@system_job`` registers the runner.

        NetBox's ``rqworker`` schedules everything in ``registry['system_jobs']``
        at startup; importing the module here ensures the decorator has run.
        """
        try:
            import netbox_nsm.analyzers.object_report.jobs  # noqa: F401
        except Exception:
            pass

    @staticmethod
    def _patch_custom_object_list_polymorphic_sort():
        from netbox_nsm.views.cot_list_table import apply_cot_polymorphic_list_table_patch

        apply_cot_polymorphic_list_table_patch()

    @staticmethod
    def _patch_color_field_widget():
        """
        Monkey-patch TextFieldType.get_form_field so that any
        CustomObjectTypeField with name='color' renders a
        ColorSelectTextWidget (picker + hex text input) instead of
        a plain CharField.
        """
        try:
            from netbox_custom_objects.field_types import TextFieldType
        except ImportError:
            return

        from netbox_nsm.forms.widgets import ColorSelectTextWidget

        _original = TextFieldType.get_form_field

        def _patched(self, field, **kwargs):
            form_field = _original(self, field, **kwargs)
            if getattr(field, "name", None) == "color":
                form_field.widget = ColorSelectTextWidget()
            return form_field

        TextFieldType.get_form_field = _patched

    @staticmethod
    def _patch_poly_subfield_labels():
        from netbox_nsm.core.poly_subfield_labels import patch_poly_subfield_labels

        patch_poly_subfield_labels()

    @staticmethod
    def _patch_cot_rule_add_index():
        from netbox_nsm.rulebooks.views.cot_rule import patch_cot_rule_add_form

        patch_cot_rule_add_form()

config = SecurityConfig  # noqa
