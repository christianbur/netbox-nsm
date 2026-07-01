"""Per-link propagation (inheritance) helpers for ObjectLink."""

from __future__ import annotations

__all__ = (
    "COT_OBJECT_LINK_PROPAGATION_CHOICES",
    "CotObjectLinkPropagationChoices",
    "LinkPropagationChoices",
    "cot_propagation_choices_for_form",
    "cot_propagation_display",
    "cot_propagation_to_native",
    "native_propagation_to_cot",
    "object_link_panel_comment",
    "object_link_panel_link_type",
    "object_link_panel_user_comment",
    "propagation_choices_for_object",
    "should_propagate_inherited_link",
    "supports_group_propagation",
    "supports_ipam_propagation",
)

from django.utils.translation import gettext_lazy as _


class LinkPropagationChoices:
    """Native propagation modes for ``nsm_object_link`` (without COT ``*_stop`` values)."""

    DIRECT = "direct"
    INHERIT_IPAM = "inherit_ipam"
    INHERIT_GROUP = "inherit_group"

    choices = (
        (DIRECT, _("Direct (bidirectional, visible on both sides)")),
        (
            INHERIT_IPAM,
            _("Inherit to IPAM children (prefixes, addresses, ranges)"),
        ),
        (INHERIT_GROUP, _("Inherit to group members")),
    )

    @classmethod
    def get_display(cls, value: str) -> str:
        return dict(cls.choices).get(value, value)


class CotObjectLinkPropagationChoices:
    """Combined propagation + stop-on-own values for ``nsm_object_link`` COT."""

    DIRECT = "direct"
    INHERIT_IPAM = "inherit_ipam"
    INHERIT_IPAM_STOP = "inherit_ipam_stop"
    INHERIT_GROUP = "inherit_group"
    INHERIT_GROUP_STOP = "inherit_group_stop"


COT_OBJECT_LINK_PROPAGATION_CHOICES = (
    CotObjectLinkPropagationChoices.DIRECT,
    CotObjectLinkPropagationChoices.INHERIT_IPAM,
    CotObjectLinkPropagationChoices.INHERIT_IPAM_STOP,
    CotObjectLinkPropagationChoices.INHERIT_GROUP,
    CotObjectLinkPropagationChoices.INHERIT_GROUP_STOP,
)

_COT_TO_NATIVE = {
    CotObjectLinkPropagationChoices.DIRECT: (
        LinkPropagationChoices.DIRECT,
        False,
    ),
    CotObjectLinkPropagationChoices.INHERIT_IPAM: (
        LinkPropagationChoices.INHERIT_IPAM,
        False,
    ),
    CotObjectLinkPropagationChoices.INHERIT_IPAM_STOP: (
        LinkPropagationChoices.INHERIT_IPAM,
        True,
    ),
    CotObjectLinkPropagationChoices.INHERIT_GROUP: (
        LinkPropagationChoices.INHERIT_GROUP,
        False,
    ),
    CotObjectLinkPropagationChoices.INHERIT_GROUP_STOP: (
        LinkPropagationChoices.INHERIT_GROUP,
        True,
    ),
}


def cot_propagation_to_native(cot_value: str) -> tuple[str, bool]:
    """Map ``nsm_object_link.propagation`` to native ObjectLink fields."""
    try:
        propagation, propagate_stop_on_own = _COT_TO_NATIVE[cot_value]
    except KeyError as exc:
        raise ValueError(f"Unknown COT propagation value: {cot_value!r}") from exc
    return propagation, propagate_stop_on_own


def native_propagation_to_cot(
    propagation: str,
    propagate_stop_on_own: bool,
) -> str:
    """Map native ObjectLink fields to ``nsm_object_link.propagation``."""
    if propagation == LinkPropagationChoices.DIRECT:
        return CotObjectLinkPropagationChoices.DIRECT
    if propagation == LinkPropagationChoices.INHERIT_IPAM:
        return (
            CotObjectLinkPropagationChoices.INHERIT_IPAM_STOP
            if propagate_stop_on_own
            else CotObjectLinkPropagationChoices.INHERIT_IPAM
        )
    if propagation == LinkPropagationChoices.INHERIT_GROUP:
        return (
            CotObjectLinkPropagationChoices.INHERIT_GROUP_STOP
            if propagate_stop_on_own
            else CotObjectLinkPropagationChoices.INHERIT_GROUP
        )
    raise ValueError(
        f"Unknown native propagation value: {propagation!r} "
        f"(stop={propagate_stop_on_own!r})"
    )


def supports_ipam_propagation(obj) -> bool:
    """True when *obj* may use ``inherit_ipam`` (container prefix)."""
    from ipam.models import Prefix

    return isinstance(obj, Prefix)


def supports_group_propagation(obj) -> bool:
    """True when *obj* may use ``inherit_group`` (COT object with ``group`` M2M)."""
    group_rel = getattr(obj, "group", None)
    if group_rel is None or not hasattr(group_rel, "all"):
        return False

    Model = type(obj)
    try:
        return Model.objects.filter(group=obj).exists()
    except Exception:
        return False


_COT_PROPAGATION_LABELS = {
    CotObjectLinkPropagationChoices.DIRECT: _(
        "Direct (bidirectional, visible on both sides)"
    ),
    CotObjectLinkPropagationChoices.INHERIT_IPAM: _(
        "Inherit to IPAM children (prefixes, addresses, ranges)"
    ),
    CotObjectLinkPropagationChoices.INHERIT_IPAM_STOP: _(
        "Inherit to IPAM children — stop when child has own link of same type"
    ),
    CotObjectLinkPropagationChoices.INHERIT_GROUP: _("Inherit to group members"),
    CotObjectLinkPropagationChoices.INHERIT_GROUP_STOP: _(
        "Inherit to group members — stop when child has own link of same type"
    ),
}


def cot_propagation_display(cot_value: str) -> str:
    """Human-readable label for a combined COT propagation value."""
    return str(_COT_PROPAGATION_LABELS.get(cot_value, cot_value))


def cot_propagation_choices_for_form(obj=None) -> list[tuple[str, str]]:
    """Combined propagation values for Assign/Edit forms (``nsm_object_link``)."""
    return [
        (value, cot_propagation_display(value))
        for value in COT_OBJECT_LINK_PROPAGATION_CHOICES
    ]


def propagation_choices_for_object(obj=None) -> list[tuple[str, str]]:
    """Propagation values shown in Assign/Edit forms (always all modes).

    *obj* is accepted for backward compatibility but no longer filters choices.
    Runtime inheritance still depends on object structure (IPAM containment or
    group membership); unsupported modes simply have no effect.
    """
    return list(LinkPropagationChoices.choices)


def object_link_panel_link_type(link) -> str:
    """Link-type column text for Security Panel direct ObjectLinks."""
    if hasattr(link, "cot_propagation"):
        return cot_propagation_display(link.cot_propagation)
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
