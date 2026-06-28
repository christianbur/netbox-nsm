"""NSM Demo Zone Matrix python bundle entrypoint.

Creates a 250\u00d7250 zone matrix in nsm_rb_zone_matrix (62,500 rules, random permit/deny).
NSM Schema must be applied first.
"""

from __future__ import annotations

from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from netbox_nsm.import_.demo import (
    DEMO_RULE_COUNT,
    DEMO_ZONE_COUNT,
    create_demo_starter_data_only,
)


def main(request=None) -> None:
    """Synchronously create the zone-matrix demo data."""
    cot = create_demo_starter_data_only()
    if request is not None:
        messages.success(
            request,
            _(
                "NSM Demo Zone Matrix created: %(zone_count)s zones, %(rule_count)s rules "
                "(random permit/deny) in '%(rb_slug)s'."
            )
            % {
                "zone_count": DEMO_ZONE_COUNT,
                "rule_count": DEMO_RULE_COUNT,
                "rb_slug": cot.slug if cot is not None else "nsm_rb_zone_matrix",
            },
        )
