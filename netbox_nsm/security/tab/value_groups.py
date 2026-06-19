"""Second-level grouping ("value") for Security tab linked objects.

The Security tab groups linked objects first by object type (e.g. a custom
object type such as *Action*) and then, within that type, by a secondary
"value" — for an *Action* object the natural value is ``Permit`` / ``Deny``.

The grouping value is derived generically from the linked object by probing a
short list of well-known attribute names so the feature works for any NSM /
NetBox object type without per-type configuration.
"""

from __future__ import annotations

__all__ = (
    "UNGROUPED_KEY",
    "UNGROUPED_LABEL",
    "VALUE_ATTR_CANDIDATES",
    "nsm_object_group_value",
)

# Attribute names probed (in order) to derive a grouping value for a linked
# object. The first non-empty match wins. ``value`` covers the typical NSM
# *Action* custom object (Permit / Deny / …); the others cover common
# alternatives so the grouping is useful across object types.
VALUE_ATTR_CANDIDATES = ("value", "action", "verdict", "decision", "policy_action")

UNGROUPED_KEY = "_none"
UNGROUPED_LABEL = "—"


def _display_for(linked, attr: str) -> str | None:
    """Return the human label for a choice-style ``attr`` if available."""
    getter = getattr(linked, f"get_{attr}_display", None)
    if not callable(getter):
        return None
    try:
        label = getter()
    except Exception:
        return None
    label = ("" if label is None else str(label)).strip()
    return label or None


def nsm_object_group_value(linked) -> tuple[str, str]:
    """Return ``(value_key, value_label)`` for second-level grouping.

    ``value_key`` is a stable, querystring-safe identifier used for filtering;
    ``value_label`` is the human-readable label shown in the UI. Objects with no
    recognisable value fall back to :data:`UNGROUPED_KEY` / :data:`UNGROUPED_LABEL`.
    """
    if linked is None:
        return UNGROUPED_KEY, UNGROUPED_LABEL
    for attr in VALUE_ATTR_CANDIDATES:
        raw = getattr(linked, attr, None)
        if raw is None:
            continue
        value = str(raw).strip()
        if not value:
            continue
        label = _display_for(linked, attr) or value
        return value, label
    return UNGROUPED_KEY, UNGROUPED_LABEL
