"""Helpers for Rulebook rules layout in changelog snapshots."""

from netbox_nsm.models import Rule
from netbox_nsm.models.rulebook import (
    _serialize_rule_group_items,
    _serialize_rule_object_items,
)


def serialize_rulebook_rules_layout(rulebook):
    """Compact rules snapshot for Rulebook changelog (dict keyed by rule pk)."""
    layout = {}
    rules = (
        Rule.objects.filter(rulebook=rulebook)
        .prefetch_related(
            "object_items__field",
            "object_items__content_type",
            "group_items__field",
            "group_items__security_group",
        )
        .order_by("index", "pk")
    )
    for rule in rules:
        layout[str(rule.pk)] = {
            "name": rule.name,
            "index": rule.index,
            "enabled": rule.enabled,
            "object_items": _serialize_rule_object_items(rule),
            "group_items": _serialize_rule_group_items(rule),
        }
    return layout
