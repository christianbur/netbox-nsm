"""Changelog helpers for NSM models."""

from __future__ import annotations

__all__ = ("apply_type_config_changelog_message",)


def describe_type_config_changes(prechange, postchange):
    lines = []
    for key, label in (
        ("sort_order", "Sort order"),
        ("display_template", "Display template"),
    ):
        old = (prechange or {}).get(key)
        new = (postchange or {}).get(key)
        if old != new:
            lines.append(f"{label}: {old!r} → {new!r}")

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
