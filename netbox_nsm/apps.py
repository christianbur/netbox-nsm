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

        # Register signal to create a second ObjectChange entry for object_b
        # whenever an NSMObjectLink is saved or deleted, so the change appears
        # in both linked objects' changelogs.
        from django.db.models.signals import post_save, post_delete
        from netbox_nsm.models import NSMObjectLink
        from netbox_nsm._changelog_signals import (
            nsm_object_link_saved,
            nsm_object_link_deleted,
        )

        post_save.connect(nsm_object_link_saved, sender=NSMObjectLink)
        post_delete.connect(nsm_object_link_deleted, sender=NSMObjectLink)
