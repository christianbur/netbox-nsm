"""
Helpers for NetBox ObjectChange / changelog integration in netbox_nsm.

Junction-table writes (rule assignments, grid inline edits) bypass a normal
``Rule.save()`` and therefore need an explicit changelog entry on the parent.
"""

from __future__ import annotations

from core.choices import ObjectChangeActionChoices
from netbox.context import current_request


def snapshot_instance(instance, *, exclude=None):
    """Return serialized state for manual pre/post change logging."""
    if hasattr(instance, "serialize_object"):
        return instance.serialize_object(exclude=exclude or ["last_updated"])
    return None


def record_object_update(instance, request, prechange_data, *, message=""):
    """
    Persist an ObjectChange for *instance* when data changed outside ``save()``.

    Used after bulk junction-table writes so the parent object's changelog
    reflects assignment changes (Rule object/group items, etc.).
    """
    req = request or current_request.get()
    if req is None:
        return

    instance._prechange_snapshot = prechange_data
    instance._changelog_message = message or ""
    objectchange = instance.to_objectchange(ObjectChangeActionChoices.ACTION_UPDATE)
    if not objectchange.has_changes:
        return

    objectchange.user = req.user
    objectchange.request_id = req.id
    objectchange.save()


def snapshot_before_edit(instance):
    """Take a pre-change snapshot when editing via custom views (not ObjectEditView)."""
    if instance.pk and hasattr(instance, "snapshot"):
        instance.snapshot()
