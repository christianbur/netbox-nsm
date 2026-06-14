"""Report address object sync issues (no fixes)."""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from netbox_nsm.objects.address_object_builder import scan_sync_state
from netbox_nsm.objects.nsm_config import resolve_object_builder_config_for_cot


class Command(BaseCommand):
    help = "Analyze nsm_address ↔ IPAM sync state and exit non-zero when issues exist."

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=("table", "json"),
            default="table",
            help="Output format (default: table).",
        )
        parser.add_argument(
            "--source",
            action="append",
            dest="sources",
            help="Limit to one IPAM source key (repeatable).",
        )

    def handle(self, *args, **options):
        try:
            from netbox_custom_objects.models import CustomObjectType
        except ImportError as exc:
            raise CommandError("netbox_custom_objects is not installed") from exc

        cot = CustomObjectType.objects.filter(slug="nsm_address").first()
        if cot is None:
            raise CommandError("COT nsm_address is not deployed")

        builder_config = resolve_object_builder_config_for_cot(cot)
        summary = scan_sync_state(builder_config, source_keys=options.get("sources"))

        if options["format"] == "json":
            payload = {
                "enabled": summary.enabled,
                "issue_count": len(summary.issues),
                "issues": [
                    {
                        "category": issue.category,
                        "source_key": issue.source_key,
                        "detail": issue.detail or str(issue),
                    }
                    for issue in summary.issues
                ],
            }
            self.stdout.write(json.dumps(payload, indent=2, default=str))
        else:
            if not summary.enabled:
                self.stdout.write("Object builder sync is disabled in nsm_config.")
            elif not summary.issues:
                self.stdout.write(self.style.SUCCESS("No sync issues found."))
            else:
                self.stdout.write(
                    f"Found {len(summary.issues)} issue(s):\n"
                )
                for issue in summary.issues:
                    self.stdout.write(f"  [{issue.category}] {issue}")

        if summary.enabled and summary.issues:
            raise SystemExit(1)
