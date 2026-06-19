"""NSM daily object report.

Reusable, REST/script-capable analysis for ``nsm_address`` /
``nsm_address_group`` Custom Objects and their IPAM links. All analysis logic
lives in Python (``object_report``); the scheduled execution wrapper lives in
``jobs`` and the read-only viewer in ``netbox_nsm.views.object_report``.

The report is intentionally **aggregated** (counts + grouped breakdowns +
bounded detail samples) so it stays correct and cheap even with > 1,000,000
address objects. No full materialization of all objects into memory or HTML.
"""
