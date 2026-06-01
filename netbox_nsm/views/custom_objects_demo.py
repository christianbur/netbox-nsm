"""Demo: create example CustomObjectTypes + objects in netbox-custom-objects.

Triggered from the Object-Builder Types tab via a button. Uses the portable
schema executor to apply a small hardcoded schema document, then creates a
few example objects through the dynamically generated models.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View

__all__ = ("CustomObjectsDemoView",)


DEMO_SCHEMA = {
    "schema_version": "1",
    "types": [
        {
            "name": "nsm_zone",
            "slug": "nsm-zone",
            "verbose_name": "NSM Zone",
            "verbose_name_plural": "NSM Zones",
            "description": "Demo zone created from netbox_nsm",
            "group_name": "NSM Demo",
            "fields": [
                {
                    "id": 1,
                    "name": "zone_name",
                    "type": "text",
                    "label": "Zone Name",
                    "primary": True,
                    "required": True,
                },
                {
                    "id": 2,
                    "name": "color",
                    "type": "text",
                    "label": "Color",
                },
                {
                    "id": 3,
                    "name": "description",
                    "type": "longtext",
                    "label": "Description",
                },
            ],
            "removed_fields": [],
        },
        {
            "name": "nsm_service",
            "slug": "nsm-service",
            "verbose_name": "NSM Service",
            "verbose_name_plural": "NSM Services",
            "description": "Demo service created from netbox_nsm",
            "group_name": "NSM Demo",
            "fields": [
                {
                    "id": 1,
                    "name": "service_name",
                    "type": "text",
                    "label": "Service Name",
                    "primary": True,
                    "required": True,
                },
                {
                    "id": 2,
                    "name": "protocol",
                    "type": "text",
                    "label": "Protocol",
                },
                {
                    "id": 3,
                    "name": "destination_ports",
                    "type": "text",
                    "label": "Destination Ports",
                },
            ],
            "removed_fields": [],
        },
    ],
}


DEMO_OBJECTS = {
    "nsm-zone": [
        {"zone_name": "LAN", "color": "green", "description": "Internal trusted"},
        {"zone_name": "DMZ", "color": "orange", "description": "Public-facing"},
        {"zone_name": "WAN", "color": "red", "description": "Internet"},
    ],
    "nsm-service": [
        {"service_name": "NTP", "protocol": "udp", "destination_ports": "123"},
        {"service_name": "SMTP", "protocol": "tcp", "destination_ports": "25"},
        {"service_name": "LDAPS", "protocol": "tcp", "destination_ports": "636"},
    ],
}


class CustomObjectsDemoView(LoginRequiredMixin, View):
    """POST-only: applies DEMO_SCHEMA and creates a few demo objects."""

    def post(self, request, *args, **kwargs):
        redirect_url = reverse("plugins:netbox_nsm:object_builder", args=["types"])

        try:
            from netbox_custom_objects.models import CustomObjectType
            from netbox_custom_objects.schema.executor import apply_document
        except ImportError:
            messages.error(
                request,
                "Plugin netbox_custom_objects ist nicht installiert.",
            )
            return redirect(redirect_url)

        try:
            with transaction.atomic():
                apply_document(DEMO_SCHEMA, allow_destructive=False)
        except Exception as exc:
            messages.error(
                request,
                f"Schema konnte nicht angewendet werden: {exc.__class__.__name__}: {exc}",
            )
            return redirect(redirect_url)

        created = 0
        skipped = 0
        for slug, rows in DEMO_OBJECTS.items():
            try:
                cot = CustomObjectType.objects.get(slug=slug)
            except CustomObjectType.DoesNotExist:
                messages.warning(request, f"CustomObjectType '{slug}' nicht gefunden.")
                continue

            model = cot.get_model()
            for row in rows:
                # Use the primary field as natural key for idempotency.
                primary_field_name = next(iter(row))
                lookup = {primary_field_name: row[primary_field_name]}
                obj, was_created = model.objects.update_or_create(
                    defaults=row, **lookup
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

        messages.success(
            request,
            (
                f"Demo angewendet: 2 CustomObjectTypes, "
                f"{created} neue Objekte erstellt, {skipped} bereits vorhanden."
            ),
        )
        return redirect(redirect_url)
