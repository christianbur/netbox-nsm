from django.utils.translation import gettext_lazy as _
from netbox.plugins import PluginConfig
from .version import __version__


class SecurityConfig(PluginConfig):
    name = "netbox_nsm"
    verbose_name = _("NetBox NSM - Network Security Management")
    description = _(
        "Document network security policy in NetBox: rulebooks, zones, NSM links, "
        "and the Security Panel (requires netbox-custom-objects)."
    )
    version = __version__
    author = "Christian Burmeister"
    author_email = ""
    base_url = "netbox-nsm"
    required_settings = []
    min_version = "4.5.0"
    max_version = "4.6.99"
    default_settings = {
        "top_level_menu": True,
        "assignments_menu": False,
        # Show NSM → Configuration → Setup (default: on)
        "setup_menu": True,
        # Setup: full sync, demo custom types, demo rulebooks (default: on)
        "setup_allow_destructive_actions": True,
        # Top-level menu and object-detail panel title (default: "Security")
        "menu_label": "",
        "panel_label": "",
    }

    def ready(self):
        super().ready()
        from netbox_nsm.core.branching_support import register_branching_models

        register_branching_models()
        self._patch_color_field_widget()
        self._patch_poly_subfield_labels()
        self._patch_cot_rule_add_index()

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
