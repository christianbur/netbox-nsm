"""Changelog helpers for NSM models."""

from __future__ import annotations

from netbox_nsm.models.type_config import PANEL_LINKABLE_DISABLED

__all__ = ("apply_type_config_changelog_message",)


def _panel_linkable_types_as_map(type_ids):
    if not type_ids:
        return {}
    if isinstance(type_ids, dict):
        return type_ids
    return {str(type_id): True for type_id in type_ids}


def describe_type_config_changes(prechange, postchange):
    lines = []
    for key, label in (
        ("matching_class", "Matching class"),
        ("display_template", "Display template"),
    ):
        old = (prechange or {}).get(key)
        new = (postchange or {}).get(key)
        if old != new:
            lines.append(f"{label}: {old!r} → {new!r}")

    pre_link = _panel_linkable_types_as_map(
        (prechange or {}).get("panel_linkable_type_ids")
    )
    post_link = _panel_linkable_types_as_map(
        (postchange or {}).get("panel_linkable_type_ids")
    )
    if PANEL_LINKABLE_DISABLED in pre_link and PANEL_LINKABLE_DISABLED not in post_link:
        lines.append("Enabled panel linkable types")
    elif PANEL_LINKABLE_DISABLED not in pre_link and PANEL_LINKABLE_DISABLED in post_link:
        lines.append("Disabled panel linkable types")
    for key in sorted(set(pre_link) | set(post_link)):
        if key == PANEL_LINKABLE_DISABLED:
            continue
        if key in pre_link and key not in post_link:
            lines.append(f"Removed linkable type {key}")
        elif key not in pre_link and key in post_link:
            lines.append(f"Added linkable type {key}")

    return "; ".join(lines)


def _snapshot_instance(instance, *, exclude=None):
    if hasattr(instance, "serialize_object"):
        exclude = exclude or ["last_updated"]
        return instance.serialize_object(exclude=exclude)
    return None


def apply_type_config_changelog_message(instance, *, prechange=None):
    """Set ``_changelog_message`` on TypeConfig before save when panel fields changed."""
    prechange = prechange or getattr(instance, "_prechange_snapshot", None)
    if not prechange:
        return
    message = describe_type_config_changes(prechange, _snapshot_instance(instance))
    if message:
        instance._changelog_message = message
