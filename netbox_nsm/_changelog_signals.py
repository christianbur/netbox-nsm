"""
Signal handlers that create additional ObjectChange records so ObjectLink
changes appear in both linked objects' changelogs.
"""

from core.choices import ObjectChangeActionChoices


def _create_related_objectchange(instance, action):
    """Create an ObjectChange for object_b of an ObjectLink."""
    from core.models import ObjectChange
    from netbox.context import current_request

    request = current_request.get()
    if request is None:
        return

    if not (instance.object_b_type_id and instance.object_b_id):
        return

    oc = ObjectChange(
        changed_object=instance,
        object_repr=str(instance)[:200],
        action=action,
        related_object_type_id=instance.object_b_type_id,
        related_object_id=instance.object_b_id,
    )
    if hasattr(instance, "_prechange_snapshot"):
        oc.prechange_data = instance._prechange_snapshot
    if action in (
        ObjectChangeActionChoices.ACTION_CREATE,
        ObjectChangeActionChoices.ACTION_UPDATE,
    ):
        oc.postchange_data = instance.serialize_object()

    try:
        oc.user = request.user
        oc.request_id = request.id
    except AttributeError:
        pass

    oc.save()


def nsm_object_link_saved(sender, instance, created, **kwargs):
    action = (
        ObjectChangeActionChoices.ACTION_CREATE
        if created
        else ObjectChangeActionChoices.ACTION_UPDATE
    )
    _create_related_objectchange(instance, action)


def nsm_object_link_deleted(sender, instance, **kwargs):
    _create_related_objectchange(instance, ObjectChangeActionChoices.ACTION_DELETE)
