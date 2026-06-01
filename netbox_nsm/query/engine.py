"""
NSM Query Engine

Evaluates parsed Query objects against SecurityPolicyRule instances.
Also computes Facets from the result set.

Design principles:
- Generic field resolution — no hard-coded field names.
- All filtering goes through this engine (policy view, global search, API).
- Rules must be pre-loaded with cached_object_items / cached_group_items.
"""

import ipaddress
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from .parser import Condition, Query


# ---------------------------------------------------------------------------
# RulebookContext — field registry for a single rulebook
# ---------------------------------------------------------------------------


class RulebookContext:
    """Pre-computed field registry for a rulebook."""

    def __init__(self, rulebook=None):
        self.rulebook = rulebook
        self._by_slug: Dict[str, Any] = {}  # lower(slug) → RulebookField
        self._by_name: Dict[str, Any] = {}  # lower(name) → RulebookField

        if rulebook:
            try:
                for f in rulebook.fields.all():
                    self._by_slug[f.slug.lower()] = f
                    self._by_name[f.name.lower()] = f
            except Exception:
                pass

    def get_field(self, name: str):
        """Look up a RulebookField by slug or display name (case-insensitive)."""
        lower = name.lower()
        return self._by_slug.get(lower) or self._by_name.get(lower)

    @property
    def facetable_fields(self) -> List:
        """All fields ordered by weight (desc) then slug (asc). Every field is facetable."""
        return sorted(
            self._by_slug.values(),
            key=lambda x: (-getattr(x, "facet_weight", 100), x.slug),
        )


# ---------------------------------------------------------------------------
# Rule caching helper — call once before filtering
# ---------------------------------------------------------------------------


def prepare_rules(rules_qs) -> List:
    """
    Load rules from a queryset (with prefetch_related already applied) and
    attach `_cached_object_items` / `_cached_group_items` lists for fast lookup.
    """
    rules = list(rules_qs)
    for rule in rules:
        rule._cached_object_items = list(rule.object_items.all())
        rule._cached_group_items = list(rule.group_items.all())
    return rules


# ---------------------------------------------------------------------------
# Fixed field resolution
# ---------------------------------------------------------------------------

_FIXED_FIELD_ALIASES: Dict[str, str] = {
    "name": "name",
    "rule": "name",
    "rule.name": "name",
    "description": "description",
    "rule.description": "description",
    "action": "policy_action",
    "rule.action": "policy_action",
    "index": "index",
    "rule.index": "index",
    "enabled": "enabled",
    "rule.enabled": "enabled",
}


def _get_fixed_value(rule, field_name: str) -> Optional[str]:
    """Return a string value for a fixed rule field, or None if not fixed."""
    attr = _FIXED_FIELD_ALIASES.get(field_name.lower())
    if attr is None:
        return None
    val = getattr(rule, attr, None)
    if val is None:
        return None
    if isinstance(val, bool):
        return "true" if val else "false"
    return str(val)


# ---------------------------------------------------------------------------
# Sub-field resolution on objects/groups
# ---------------------------------------------------------------------------


def _get_sub_field_values(obj, sub_field: Optional[str]) -> List[str]:
    """Resolve sub_field on a NetBox object or SecurityObjectGroup."""
    if obj is None:
        return []

    sf = (sub_field or "name").lower()

    # --- name / labels ---
    if sf in ("name", "label", "labels"):
        # For labels, try a `labels` attribute, ManyToMany tags, or fall back to name.
        if sf in ("label", "labels"):
            attr = getattr(obj, "labels", None)
            if attr is not None:
                if hasattr(attr, "all"):
                    return [str(l) for l in attr.all()]
                return [str(attr)]
            tags_attr = getattr(obj, "tags", None)
            if tags_attr is not None and hasattr(tags_attr, "all"):
                tag_names = [str(t) for t in tags_attr.all()]
                if tag_names:
                    return tag_names
        return [str(getattr(obj, "name", "") or obj)]

    # --- address / prefix ---
    if sf in ("address", "prefix", "ip", "network"):
        for attr_name in ("address", "prefix", "host"):
            val = getattr(obj, attr_name, None)
            if val is not None:
                return [str(val)]
        return []

    # --- generic attribute lookup ---
    val = getattr(obj, sf, None)
    if val is None:
        return []
    if hasattr(val, "all"):  # ManyToMany / queryset
        return [str(v) for v in val.all()]
    return [str(val)]


def _get_field_values(rule, field, sub_field: Optional[str]) -> List[str]:
    """Collect all sub-field values for a RulebookField within a rule."""
    values: List[str] = []
    field_pk = field.pk

    for item in getattr(rule, "_cached_object_items", []):
        if item.field_id != field_pk:
            continue
        values.extend(_get_sub_field_values(item.assigned_object, sub_field))

    for item in getattr(rule, "_cached_group_items", []):
        if item.field_id != field_pk:
            continue
        values.extend(_get_sub_field_values(item.security_group, sub_field))

    return values


# ---------------------------------------------------------------------------
# Operator evaluation
# ---------------------------------------------------------------------------


def _apply_operator(actual: List[str], operator: str, query_val) -> bool:
    """Apply a comparison operator to a list of actual values."""
    has_values = len(actual) > 0

    if operator == "exists":
        return has_values

    if operator == "!exists":
        return not has_values

    if not has_values:
        # No values → "!=" and "notin" succeed (nothing to match against)
        return operator in ("!=", "notin")

    if operator == "=":
        qv_lower = query_val.lower() if query_val else ""
        return any(v.lower() == qv_lower for v in actual)

    if operator == "!=":
        qv_lower = query_val.lower() if query_val else ""
        return not any(v.lower() == qv_lower for v in actual)

    if operator == "contains":
        qv_lower = (query_val or "").lower()
        # String contains
        if any(qv_lower in v.lower() for v in actual):
            return True
        # IP containment: does any value (prefix/network) contain query_val (host)?
        try:
            target_ip = ipaddress.ip_address(query_val)
            for v in actual:
                try:
                    net = ipaddress.ip_network(v, strict=False)
                    if target_ip in net:
                        return True
                except ValueError:
                    pass
        except ValueError:
            pass
        return False

    if operator == "in":
        q_set = {(qv or "").lower() for qv in (query_val or [])}
        return any(v.lower() in q_set for v in actual)

    if operator == "notin":
        q_set = {(qv or "").lower() for qv in (query_val or [])}
        return not any(v.lower() in q_set for v in actual)

    return False


# ---------------------------------------------------------------------------
# Condition evaluation
# ---------------------------------------------------------------------------


def _evaluate_condition(rule, condition: Condition, context: RulebookContext) -> bool:
    """Evaluate a single Condition against a rule."""
    fixed_val = _get_fixed_value(rule, condition.field)
    if fixed_val is not None:
        return _apply_operator([fixed_val], condition.operator, condition.value)

    # Try to resolve as a RulebookField
    rb_field = context.get_field(condition.field)
    if rb_field is None:
        # Unknown field — never matches (don't silently pass through)
        return False

    values = _get_field_values(rule, rb_field, condition.sub_field)
    return _apply_operator(values, condition.operator, condition.value)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def filter_rules(rules: List, query: Query, context: RulebookContext) -> List:
    """
    Filter a list of pre-loaded rules using a parsed Query.

    Rules must have `_cached_object_items` and `_cached_group_items` attached
    (use `prepare_rules()` first).

    Returns the original list unchanged if the query is empty or invalid.
    """
    if not query.is_active:
        return list(rules)

    return [
        rule
        for rule in rules
        if all(_evaluate_condition(rule, cond, context) for cond in query.conditions)
    ]


def compute_facets(rules: List, context: RulebookContext) -> List[Dict]:
    """
    Compute facet entries from the current (already filtered) rule set.

    Returns a list of facet dicts ordered by field facet_weight (desc):
    [
        {
            "field_slug": "source",
            "field_name": "Source",
            "facet_mode": "value",
            "entries": [{"value": "Web", "count": 44}, ...],
        },
        ...
    ]
    """
    facets = []

    # ── Fixed: Status facet ──────────────────────────────────────────────
    status_counts: Counter = Counter()
    for rule in rules:
        status_counts["Enabled" if getattr(rule, "enabled", True) else "Disabled"] += 1
    if status_counts:
        status_entries = [
            {
                "value": val,
                "count": cnt,
                "qval": (
                    'Enabled == "true"' if val == "Enabled" else 'Enabled == "false"'
                ),
            }
            for val, cnt in status_counts.most_common()
        ]
        facets.append(
            {
                "field_slug": "_status",
                "field_name": "Status",
                "facet_mode": "value",
                "facet_weight": 9999,
                "entries": status_entries,
                "entries_value": status_entries,
                "entries_set": status_entries,
            }
        )

    for field in context.facetable_fields:
        counter_value: Counter = Counter()
        counter_set: Counter = Counter()

        for rule in rules:
            values = _get_field_values(rule, field, "name")
            # value mode: count each distinct value once per rule
            for v in set(values):
                counter_value[v] += 1
            # set mode: treat the whole set as one combined key
            if values:
                key = ", ".join(sorted(set(values)))
                counter_set[key] += 1

        if not counter_value:
            continue

        field_path = f"{field.name}.Name" if True else field.name

        def make_entries(counter):
            result = []
            for val, cnt in counter.most_common(100):
                qval = f'{field_path} = "{val}"'
                result.append({"value": val, "count": cnt, "qval": qval})
            return result

        facets.append(
            {
                "field_slug": field.slug,
                "field_name": field.name,
                "facet_mode": getattr(field, "facet_mode", "value"),
                "facet_weight": getattr(field, "facet_weight", 100),
                "entries": make_entries(counter_value),
                "entries_value": make_entries(counter_value),
                "entries_set": make_entries(counter_set),
            }
        )

    return facets


def global_search(rules_qs, query: Query) -> Dict:
    """
    Search all rulebooks using the query engine.

    Loads all matching rules (with prefetch), groups by rulebook,
    returns a dict:
    {
        "rulebook_groups": [
            {"rulebook": <obj>, "count": 15, "policy_url": "..."},
            ...
        ],
        "total_count": 37,
    }
    """
    from collections import defaultdict
    from django.urls import reverse

    # Load and prepare all rules
    rules = prepare_rules(
        rules_qs.prefetch_related(
            "object_items__field",
            "object_items__content_type",
            "group_items__field",
            "group_items__security_group",
        ).select_related("rulebook")
    )

    # Group rules by rulebook for per-rulebook context
    by_rulebook: Dict = defaultdict(list)
    for rule in rules:
        by_rulebook[rule.rulebook].append(rule)

    result_groups = []
    total_count = 0

    for rulebook, rb_rules in sorted(
        by_rulebook.items(), key=lambda x: x[0].name if x[0] else ""
    ):
        ctx = RulebookContext(rulebook)
        matched = filter_rules(rb_rules, query, ctx)
        if not matched:
            continue

        try:
            policy_url = (
                reverse(
                    "plugins:netbox_nsm:securitypolicyrulebook_policy",
                    args=[rulebook.pk],
                )
                + f"?nsm_q={query.to_string()}"
            )
        except Exception:
            policy_url = ""

        result_groups.append(
            {
                "rulebook": rulebook,
                "count": len(matched),
                "policy_url": policy_url,
            }
        )
        total_count += len(matched)

    return {"rulebook_groups": result_groups, "total_count": total_count}
