import os
from django.apps import AppConfig


class NetBoxSecurityConfig(AppConfig):
    name = "netbox_nsm"

    def ready(self):
        from django.conf import settings

        locale_path = os.path.join(os.path.dirname(__file__), "locale")
        if locale_path not in list(getattr(settings, "LOCALE_PATHS", [])):
            settings.LOCALE_PATHS = list(getattr(settings, "LOCALE_PATHS", [])) + [
                locale_path
            ]

        from netbox_nsm.core.setup_flags import sync_setup_menu_config_state

        sync_setup_menu_config_state()
