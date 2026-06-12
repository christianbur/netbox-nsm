"""Populate ``CustomObjectType.comments`` with bundled ``nsm_config`` YAML."""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Write bundled nsm_config YAML into CustomObjectType.comments for all "
        "nine UI object types (zones, addresses, services, …)."
    )

    def handle(self, *args, **options):
        try:
            from netbox_custom_objects.models import CustomObjectType  # noqa: F401
        except ImportError:
            self.stderr.write(
                self.style.ERROR("Plugin netbox_custom_objects is not installed.")
            )
            return

        from netbox_nsm.objects.type_config_export import backfill_cot_nsm_config_comments

        updated = backfill_cot_nsm_config_comments()
        self.stdout.write(
            self.style.SUCCESS(
                f"Synced nsm_config comments on {updated} Custom Object Type(s)."
            )
        )
