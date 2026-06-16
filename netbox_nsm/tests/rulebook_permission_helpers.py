"""Test helpers for per-COT rulebook and object-link permissions."""

__all__ = (
    "grant_nsm_config_perms",
    "grant_object_link_perms",
    "grant_rulebook_cot_perms",
    "grant_rulebook_list_access",
)


def grant_nsm_config_perms(testcase, *, view=False, change=False):
    """Grant netbox-custom-objects permissions for Object Config / nsm_config."""
    perms = []
    if view:
        perms.append("netbox_custom_objects.view_customobjecttype")
    if change:
        perms.append("netbox_custom_objects.change_customobjecttype")
    if perms:
        testcase.add_permissions(*perms)


def grant_rulebook_cot_perms(testcase, cot, *, view=True, change=False, add=False, delete=False):
    """Grant netbox-custom-objects permissions on a rulebook COT's rule model."""
    model = cot.get_model()
    model_name = model._meta.model_name
    perms = []
    if view:
        perms.append(f"netbox_custom_objects.view_{model_name}")
    if change:
        perms.append(f"netbox_custom_objects.change_{model_name}")
    if add:
        perms.append(f"netbox_custom_objects.add_{model_name}")
    if delete:
        perms.append(f"netbox_custom_objects.delete_{model_name}")
    if perms:
        testcase.add_permissions(*perms)


def grant_object_link_perms(testcase, *, view=False, add=True, change=False, delete=False):
    """Grant netbox-custom-objects permissions on the ``nsm_object_link`` COT model."""
    from netbox_nsm.objects.object_link_service import object_link_permission

    perms = []
    for action, enabled in (
        ("view", view),
        ("add", add),
        ("change", change),
        ("delete", delete),
    ):
        if not enabled:
            continue
        perm = object_link_permission(action)
        if perm:
            perms.append(perm)
    if perms:
        testcase.add_permissions(*perms)


def grant_rulebook_list_access(testcase):
    """Ensure the user may open the rulebook list (per-COT view permission)."""
    from netbox_custom_objects.models import CustomObjectType

    from netbox_nsm.rulebooks.templates import RULEBOOK_GROUP

    cot = (
        CustomObjectType.objects.filter(group_name=RULEBOOK_GROUP)
        .order_by("pk")
        .first()
    )
    if cot is None:
        cot = CustomObjectType.objects.create(
            name="nsm_rb_list_access_helper",
            slug="nsm_rb_list_access_helper",
            verbose_name="List Access Helper",
            group_name=RULEBOOK_GROUP,
        )
    grant_rulebook_cot_perms(testcase, cot, view=True)
    return cot
