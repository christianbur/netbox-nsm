"""Align deployed rulebook COT verbose names to ``Rulebook <name>`` format."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from netbox_nsm.rulebooks.create import format_rulebook_display_name
from netbox_nsm.rulebooks.templates import RULEBOOK_GROUP, is_deployed_rulebook_slug


class Command(BaseCommand):
    help = (
        "Set verbose_name and verbose_name_plural to the same "
        '"Rulebook <name>" label for deployed NSM rulebooks.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print planned changes without saving.",
        )
        parser.add_argument(
            "--slug",
            dest="slug",
            help="Only fix this rulebook slug (e.g. nsm_rb_test01).",
        )
        parser.add_argument(
            "--normalize",
            action="store_true",
            help=(
                'Rewrite verbose_name to "Rulebook <slug suffix>" '
                "(default: keep existing verbose_name, sync plural only)."
            ),
        )

    def handle(self, *args, **options):
        from netbox_custom_objects.models import CustomObjectType

        dry_run = options["dry_run"]
        normalize = options["normalize"]
        slug_filter = (options.get("slug") or "").strip()

        queryset = CustomObjectType.objects.filter(group_name=RULEBOOK_GROUP)
        if slug_filter:
            queryset = queryset.filter(slug=slug_filter)

        updated = 0
        for cot in queryset.order_by("slug"):
            if not is_deployed_rulebook_slug(cot.slug):
                continue

            suffix = cot.slug.removeprefix("nsm_rb_").replace("_", " ")
            if normalize:
                target = format_rulebook_display_name(suffix)
            else:
                target = (cot.verbose_name or "").strip() or format_rulebook_display_name(
                    suffix
                )
            current_plural = cot.verbose_name_plural or ""
            if cot.verbose_name == target and current_plural == target:
                continue

            self.stdout.write(
                f"{cot.slug}: "
                f"verbose_name={cot.verbose_name!r} -> {target!r}, "
                f"verbose_name_plural={current_plural!r} -> {target!r}"
            )
            if not dry_run:
                cot.verbose_name = target
                cot.verbose_name_plural = target
                cot.save(update_fields=["verbose_name", "verbose_name_plural"])
            updated += 1

        if updated:
            prefix = "Would update" if dry_run else "Updated"
            self.stdout.write(self.style.SUCCESS(f"{prefix} {updated} rulebook(s)."))
        else:
            self.stdout.write("No rulebooks needed changes.")
