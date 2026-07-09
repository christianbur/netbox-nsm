"""Populate ``CustomObjectType.comments`` with bundled ``nsm_config`` YAML."""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Write bundled nsm_config YAML from nsm_schema.json into "
        "CustomObjectType.comments for all metadata types."
    )

    def handle(self, *args, **options):
        try:
            from netbox_custom_objects.models import CustomObjectType  # noqa: F401
        except ImportError:
            self.stderr.write(
                self.style.ERROR("Plugin netbox_custom_objects is not installed.")
            )
            return

        from netbox_nsm.type_metadata.config import apply_schema_bundle_metadata

        counts = apply_schema_bundle_metadata()
        updated = counts.get("types", 0) + counts.get("rulebooks", 0)
        self.stdout.write(
            self.style.SUCCESS(
                f"Synced nsm_config comments for {updated} Custom Object Type(s) "
                f"({counts.get('types', 0)} types, {counts.get('rulebooks', 0)} rulebooks)."
            )
        )
