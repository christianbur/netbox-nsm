"""Per-COT rulebook permissions via netbox-custom-objects rule models."""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from netbox_nsm.rulebooks.registry import iter_deployed_cot_rulebooks

__all__ = (
    "RulebookListProxy",
    "can_add_rulebook_rules",
    "can_change_rulebook",
    "can_create_rulebook",
    "can_delete_deployed_rulebook",
    "can_delete_rulebook_rules",
    "can_show_rulebook_delete",
    "can_view_rulebook",
    "filter_viewable_rulebook_rows",
    "rulebook_permission",
    "user_can_access_rulebooks",
)

_CREATE_COT = "netbox_custom_objects.add_customobjecttype"
_DELETE_COT = "netbox_custom_objects.delete_customobjecttype"


class RulebookListProxy(models.Model):
    """Unmanaged shim for rulebook list NetBoxTable / object_list templates."""

    _netbox_private = True

    class Meta:
        managed = False
        default_permissions = ()
        verbose_name = _("Rulebook")
        verbose_name_plural = _("Rulebooks")


def rulebook_permission(cot, action: str) -> str | None:
    """Return ``netbox_custom_objects.{action}_{model}`` for rule rows, or ``None``."""
    try:
        model = cot.get_model()
    except Exception:
        return None
    if model is None:
        return None
    return f"netbox_custom_objects.{action}_{model._meta.model_name}"


def can_view_rulebook(user, cot) -> bool:
    perm = rulebook_permission(cot, "view")
    return bool(perm and user.has_perm(perm))


def can_change_rulebook(user, cot) -> bool:
    for action in ("change", "add"):
        perm = rulebook_permission(cot, action)
        if perm and user.has_perm(perm):
            return True
    return False


def can_add_rulebook_rules(user, cot) -> bool:
    perm = rulebook_permission(cot, "add")
    return bool(perm and user.has_perm(perm))


def can_delete_rulebook_rules(user, cot) -> bool:
    perm = rulebook_permission(cot, "delete")
    return bool(perm and user.has_perm(perm))


def can_delete_deployed_rulebook(user, cot, *, rule_count: int) -> bool:
    """May delete the deployed rulebook COT (no blockers, permission granted)."""
    if not user.has_perm(_DELETE_COT):
        return False
    from netbox_nsm.rulebooks.delete_blockers import deployed_rulebook_delete_blockers

    return not deployed_rulebook_delete_blockers(cot, rule_count=rule_count)


def can_show_rulebook_delete(user) -> bool:
    """May open the rulebook delete flow (dropdown entry)."""
    return user.has_perm(_DELETE_COT)


def can_create_rulebook(user) -> bool:
    return user.has_perm(_CREATE_COT)


def user_can_access_rulebooks(user) -> bool:
    """May open the rulebook list (rows are filtered separately)."""
    if can_create_rulebook(user):
        return True
    for cot in iter_deployed_cot_rulebooks():
        if can_view_rulebook(user, cot):
            return True
    return False


def filter_viewable_rulebook_rows(rows, user):
    """Return only virtual rulebook rows the user may view."""
    return [row for row in rows if can_view_rulebook(user, row.cot)]
