"""Copy native ``ObjectLink`` rows into COT ``nsm_object_link`` instances."""

from __future__ import annotations

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from netbox_nsm.security.links.link_propagation import native_propagation_to_cot
from netbox_nsm.security.links.object_link_service import (
    NSM_OBJECT_LINK_SLUG,
    classify_link_endpoints,
    get_object_link_model,
    link_name_for_endpoints,
)


class Command(BaseCommand):
    help = (
        "Migrate native netbox_nsm_objectlink rows to COT nsm_object_link instances."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report actions without writing COT rows.",
        )
        parser.add_argument(
            "--delete-native",
            action="store_true",
            help="Delete native ObjectLink rows after successful COT copy.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        delete_native = options["delete_native"]
        model = get_object_link_model()
        if model is None:
            self.stderr.write(
                self.style.ERROR(
                    f"COT {NSM_OBJECT_LINK_SLUG!r} is not deployed. "
                    "Apply the NSM Schema bundle first (Security → Configuration → Bundles)."
                )
            )
            return

        try:
            ObjectLink = apps.get_model("netbox_nsm", "ObjectLink")
        except LookupError:
            self.stderr.write(
                self.style.WARNING(
                    "Native ObjectLink model already removed (migration applied)."
                )
            )
            return

        qs = ObjectLink.objects.select_related("object_a_type", "object_b_type").order_by(
            "pk"
        )
        total = qs.count()
        if total == 0:
            self.stdout.write("No native ObjectLink rows to migrate.")
            return

        created = 0
        updated = 0
        skipped = 0
        deleted = 0

        with transaction.atomic():
            for link in qs.iterator():
                object_a = link.object_a
                object_b = link.object_b
                if object_a is None or object_b is None:
                    skipped += 1
                    self.stdout.write(
                        f"  skip pk={link.pk}: unresolved GFK endpoint(s)"
                    )
                    continue

                netbox, policy = classify_link_endpoints(object_a, object_b)
                cot_propagation = native_propagation_to_cot(
                    link.propagation, link.propagate_stop_on_own
                )
                filt = {
                    "netbox_object_content_type": ContentType.objects.get_for_model(
                        netbox
                    ),
                    "netbox_object_object_id": netbox.pk,
                    "policy_object_content_type": ContentType.objects.get_for_model(
                        policy
                    ),
                    "policy_object_object_id": policy.pk,
                }
                existing = model.objects.filter(**filt).first()
                name = link_name_for_endpoints(netbox, policy)

                if dry_run:
                    action = "update" if existing else "create"
                    self.stdout.write(
                        f"  [{action}] native pk={link.pk} → "
                        f"netbox={netbox!r} policy={policy!r} "
                        f"propagation={cot_propagation!r}"
                    )
                    if existing:
                        updated += 1
                    else:
                        created += 1
                    continue

                if existing is not None:
                    existing.propagation = cot_propagation
                    existing.comment = link.comment or ""
                    existing.name = name
                    existing.save(
                        update_fields=["propagation", "comment", "name", "last_updated"]
                    )
                    updated += 1
                else:
                    model.objects.create(
                        name=name,
                        netbox_object=netbox,
                        policy_object=policy,
                        propagation=cot_propagation,
                        comment=link.comment or "",
                    )
                    created += 1

                if delete_native:
                    link.delete()
                    deleted += 1

            if dry_run:
                transaction.set_rollback(True)

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Migrated {total} native row(s): "
                f"{created} created, {updated} updated, {skipped} skipped"
                + (f", {deleted} native deleted" if delete_native and not dry_run else "")
            )
        )
