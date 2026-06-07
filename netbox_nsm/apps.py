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
        # whenever an ObjectLink is saved or deleted, so the change appears
        # in both linked objects' changelogs.
        from django.db.models.signals import post_save, post_delete
        from netbox_nsm.models import ObjectLink
        from netbox_nsm._changelog_signals import (
            nsm_object_link_saved,
            nsm_object_link_deleted,
        )

        post_save.connect(nsm_object_link_saved, sender=ObjectLink)
        post_delete.connect(nsm_object_link_deleted, sender=ObjectLink)

        from django.db.models.signals import post_save as _post_save
        from netbox_nsm.models import Rulebook
        from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields

        def _ensure_system_fields(sender, instance, **kwargs):
            ensure_system_rulebook_fields(instance)

        _post_save.connect(
            _ensure_system_fields,
            sender=Rulebook,
            dispatch_uid="netbox_nsm_ensure_system_rulebook_fields",
        )

        from netbox_nsm.setup_flags import sync_setup_menu_config_state

        sync_setup_menu_config_state()
