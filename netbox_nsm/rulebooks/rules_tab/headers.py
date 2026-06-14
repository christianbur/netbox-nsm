from __future__ import annotations

def rules_field_display_label(
    field_label: str, field_group: str = "", *, cot=None
) -> str:
    """Combine COT field label and UI group, e.g. Zones + Source → Zones (Source)."""
    from netbox_nsm.rulebooks.rulebook_groups import resolve_group_name_for_display

    label = (field_label or "").strip()
    group = resolve_group_name_for_display(field_group, cot=cot)
    if label and group and group != label:
        return f"{label} ({group})"
    return label or group


def rules_object_column_display_label(
    child_header: str, group_header: str, *, group_in_parens: bool = True
) -> str:
    """Build object column title, e.g. Zones (Source)."""
    title, _subtitle = rules_object_column_header_parts(
        child_header, group_header, group_in_parens=group_in_parens
    )
    return title


def _group_header_is_field_label(group_header: str) -> bool:
    """True when *group_header* is a full field label, not just Source/Destination."""
    group = (group_header or "").strip()
    if not group:
        return False
    if "(" in group:
        return True
    return len(group.split()) > 1 or "&" in group


def rules_object_column_header_parts(
    child_header: str,
    group_header: str = "",
    *,
    field_label: str = "",
    field_group: str = "",
    group_in_parens: bool = True,
) -> tuple[str, str]:
    """Return (title, subtitle) for two-line object column headers.

    *title* — field context, e.g. ``Addresses (Source)`` (small in expanded thead).
    *subtitle* — object/COT type name, e.g. ``Address`` (bold in expanded thead).
    """
    type_label = (child_header or "").strip()
    label = (field_label or "").strip()
    group = (field_group or "").strip()
    legacy_group = (group_header or "").strip()

    if label:
        title = rules_field_display_label(label, group)
        subtitle = type_label or label
        return title, subtitle

    if _group_header_is_field_label(legacy_group):
        title = legacy_group
        subtitle = type_label or legacy_group
        return title, subtitle

    if group_in_parens and type_label and legacy_group and legacy_group != type_label:
        from netbox_nsm.rulebooks.rulebook_groups import resolve_group_name_for_display

        group_suffix = resolve_group_name_for_display(legacy_group) or legacy_group
        title = (
            f"{type_label} ({group_suffix})"
            if group_suffix and group_suffix != type_label
            else type_label
        )
    else:
        title = type_label or legacy_group
    subtitle = type_label or legacy_group
    return title, subtitle


def rules_object_column_accessible_label(title: str, subtitle: str) -> str:
    """Single-line label for aria/filter when header uses title + subtitle."""
    title = (title or "").strip()
    subtitle = (subtitle or "").strip()
    if title and subtitle and title != subtitle:
        return f"{subtitle}, {title}"
    return title or subtitle
