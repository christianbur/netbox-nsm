"""NSM Demo Zone/Address/AdressGroup python bundle entrypoint.

Queues the address bench (50,000 addresses) via RQ.  Requires a running RQ worker.
NSM Schema must be applied first.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from netbox_nsm.import_.demo import (
    SCALE_DEMO_50K_IMPORT,
    SCALE_DEMO_50K_RULEBOOK_NAME,
    _queue_demo_import,
)


def main(request=None) -> None:
    """Queue the address bench demo in the default RQ worker."""
    if request is None:
        raise RuntimeError(
            "nsm_demo_zone_address_adressgroup requires a request context "
            "(needs RQ worker access via django_rq)."
        )
    _queue_demo_import(
        request,
        import_path=SCALE_DEMO_50K_IMPORT,
        label=_("NSM Demo Zone/Address/AdressGroup"),
        rulebook_name=SCALE_DEMO_50K_RULEBOOK_NAME,
        job_timeout=3600,
        processing_minutes="5\u201315",
    )
