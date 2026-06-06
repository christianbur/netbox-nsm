"""Per-link propagation (inheritance) helpers for ObjectLink."""

from __future__ import annotations

__all__ = (
    "object_link_panel_comment",
    "object_link_panel_link_type",
    "object_link_panel_user_comment",
    "propagation_choices_for_object",
    "should_propagate_inherited_link",
    "supports_group_propagation",
    "supports_ipam_propagation",
)

from netbox_nsm.models.object_link import LinkPropagationChoices


def supports_ipam_propagation(obj) -> bool:
    """True when *obj* may use ``inherit_ipam`` (container prefix)."""
    from ipam.models import Prefix

    return isinstance(obj, Prefix)


def supports_group_propagation(obj) -> bool:
    """True when *obj* may use ``inherit_group`` (group / ObjectGroup)."""
    from netbox_nsm.models import ObjectGroup

    if isinstance(obj, ObjectGroup):
        return True

    group_rel = getattr(obj, "group", None)
    if group_rel is None or not hasattr(group_rel, "all"):
        return False

    Model = type(obj)
    try:
        return Model.objects.filter(group=obj).exists()
    except Exception:
        return False


def propagation_choices_for_object(obj) -> list[tuple[str, str]]:
    """Allowed propagation values for Assign on *obj*."""
    choices: list[tuple[str, str]] = [
        (LinkPropagationChoices.DIRECT, LinkPropagationChoices.DIRECT.label),
    ]
    if supports_ipam_propagation(obj):
        choices.append(
            (
                LinkPropagationChoices.INHERIT_IPAM,
                LinkPropagationChoices.INHERIT_IPAM.label,
            )
        )
    if supports_group_propagation(obj):
        choices.append(
            (
                LinkPropagationChoices.INHERIT_GROUP,
                LinkPropagationChoices.INHERIT_GROUP.label,
            )
        )
    return choices


def object_link_panel_link_type(link) -> str:
    """Link-type column text for Security Panel direct ObjectLinks."""
    from django.utils.translation import gettext as _

    parts = [str(link.get_propagation_display())]
    if link.propagate_stop_on_own:
        parts.append(str(_("stop on own")))
    return " · ".join(parts)


def object_link_panel_user_comment(link) -> str:
    """User comment only (excludes link type / propagation)."""
    return (link.comment or "").strip()


def object_link_panel_comment(link) -> str:
    """Combined link type + user comment (legacy helper)."""
    parts = [object_link_panel_link_type(link)]
    user_comment = object_link_panel_user_comment(link)
    if user_comment:
        parts.append(user_comment)
    return " · ".join(parts)


def should_propagate_inherited_link(
    link,
    type_key: str,
    covered_type_keys: set[str],
    *,
    expected_propagation: str,
) -> bool:
    """Return whether *link* should yield an inherited row for *type_key*."""
    if (
        getattr(link, "propagation", LinkPropagationChoices.DIRECT)
        != expected_propagation
    ):
        return False
    if link.propagate_stop_on_own and type_key in covered_type_keys:
        return False
    return True
