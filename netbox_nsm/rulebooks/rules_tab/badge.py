from __future__ import annotations

def format_rules_tab_badge(
    filtered_count: int,
    total_count: int,
    *,
    filter_active: bool,
) -> int | str:
    """Rules nav-tab badge: ``filtered/total`` when filters apply, else total only."""
    if filter_active:
        return f"{filtered_count}/{total_count}"
    return total_count


def rules_tab_badge_for_object(obj) -> int | str | None:
    """Badge value for virtual rulebook tab navigation."""
    badge = getattr(obj, "rules_tab_badge", None)
    if badge is not None and badge != "":
        return badge
    rule_count = getattr(obj, "rule_count", None)
    return rule_count if rule_count is not None else None
