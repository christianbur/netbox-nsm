from django.utils.translation import gettext_lazy as _
from netbox.plugins import PluginConfig
from .version import __version__


class SecurityConfig(PluginConfig):
    name = "netbox_nsm"
    verbose_name = _("NetBox NSM - Network Security Management")
    description = _("A NetBox plugin for network security and NAT management")
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


config = SecurityConfig  # noqa
