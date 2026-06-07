"""Helpers for Rulebook rules layout in changelog snapshots."""

from netbox_nsm.branch_db import branch_db_alias
from netbox_nsm.models import Rule
from netbox_nsm.models.rulebook import (
    _serialize_rule_group_items,
    _serialize_rule_object_items,
)

_RULE_CHANGELOG_PREFETCH = (
    "object_items__field",
    "object_items__content_type",
    "group_items__field",
    "group_items__security_group",
)


def serialize_rule_layout_entry(rule):
    """Compact snapshot for a single rule (changelog delta)."""
    return {
        "name": rule.name,
        "index": rule.index,
        "enabled": rule.enabled,
        "object_items": _serialize_rule_object_items(rule),
        "group_items": _serialize_rule_group_items(rule),
    }


def _rules_queryset(*, db_alias=None):
    qs = Rule.objects.all()
    alias = db_alias if db_alias is not None else branch_db_alias()
    if alias:
        qs = qs.using(alias)
    return qs


def snapshot_rule_layout_entry(rule, *, db_alias=None):
    """Return ``{"rules_layout": {pk: entry}}`` for one rule."""
    rule = (
        _rules_queryset(db_alias=db_alias)
        .filter(pk=rule.pk)
        .prefetch_related(*_RULE_CHANGELOG_PREFETCH)
        .get()
    )
    return {"rules_layout": {str(rule.pk): serialize_rule_layout_entry(rule)}}


def snapshot_rules_layout_entries(rules):
    """Return ``{"rules_layout": {...}}`` for the given rule queryset."""
    if hasattr(rules, "prefetch_related"):
        rules = rules.prefetch_related(*_RULE_CHANGELOG_PREFETCH)
    layout = {}
    for rule in rules:
        layout[str(rule.pk)] = serialize_rule_layout_entry(rule)
    return {"rules_layout": layout}


def serialize_rulebook_rules_layout(rulebook):
    """Compact rules snapshot for Rulebook changelog (dict keyed by rule pk)."""
    rules = Rule.objects.filter(rulebook=rulebook)
    db_alias = branch_db_alias()
    if db_alias:
        rules = rules.using(db_alias)
    rules = rules.prefetch_related(*_RULE_CHANGELOG_PREFETCH).order_by("index", "pk")
    layout = {}
    for rule in rules:
        layout[str(rule.pk)] = serialize_rule_layout_entry(rule)
    return layout
