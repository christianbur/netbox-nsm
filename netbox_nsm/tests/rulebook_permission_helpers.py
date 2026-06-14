"""Test helpers for per-COT rulebook permissions."""

__all__ = ("grant_rulebook_cot_perms",)


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
