from django.utils.translation import gettext_lazy as _
from netbox.plugins import PluginConfig
from .version import __version__


class SecurityConfig(PluginConfig):
    name = "netbox_nsm"
    verbose_name = _("NetBox NSM - Network Security Management")
    description = _(
        "A NetBox plugin for network security management, including object groups and security policies."
    )
    version = __version__
    author = "Christian Burmeister"
    author_email = ""
    base_url = "netbox-nsm"
    required_settings = []
    min_version = "4.5.0"
    default_settings = {
        "top_level_menu": True,
        "assignments_menu": False,
        "virtual_ext_page": "left",
        "interface_ext_page": "full_width",
        "address_ext_page": "right",
    }

    def ready(self):
        super().ready()
        self._patch_color_field_widget()

    @staticmethod
    def _patch_color_field_widget():
        """
        Monkey-patch TextFieldType.get_form_field so that any
        CustomObjectTypeField with name='color' renders a
        ColorSelectTextWidget (picker + hex text input) instead of
        a plain CharField.
        """
        from netbox_custom_objects.field_types import TextFieldType
        from netbox_nsm.forms.widgets import ColorSelectTextWidget

        _original = TextFieldType.get_form_field

        def _patched(self, field, **kwargs):
            form_field = _original(self, field, **kwargs)
            if getattr(field, "name", None) == "color":
                form_field.widget = ColorSelectTextWidget()
            return form_field

        TextFieldType.get_form_field = _patched


config = SecurityConfig  # noqa
