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
import re
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
        # (field_pk, content_type_id) → set of lower(matching_class) for that type
        self._ct_classes: Dict[tuple, set] = {}
        # (field_pk, content_type_id) → display label (str(TypeConfig))
        self._ct_group_label: Dict[tuple, str] = {}
        # field_pk → ordered list of distinct group labels (by sort_order)
        self._field_group_order: Dict[int, List[str]] = {}

        if rulebook:
            try:
                fields_qs = rulebook.fields.prefetch_related(
                    "type_configs__type_config__content_type"
                ).all()
                for f in fields_qs:
                    self._by_slug[f.slug.lower()] = f
                    self._by_name[f.name.lower()] = f
                    # also register stripped name (without trailing parenthetical) as alias
                    stripped = re.sub(r'\s*\(.*?\)\s*$', '', f.name).strip().lower()
                    if stripped != f.name.lower():
                        self._by_name[stripped] = f
                    for ftc in sorted(f.type_configs.all(), key=lambda x: x.sort_order):
                        tc = ftc.type_config
                        ct = tc.content_type
                        key = (f.pk, ct.pk)
                        mc = (getattr(tc, "matching_class", None) or "").lower()
                        self._ct_classes.setdefault(key, set())
                        if mc:
                            self._ct_classes[key].add(mc)
                        tc_label = str(tc)
                        self._ct_group_label[key] = tc_label
                        order_list = self._field_group_order.setdefault(f.pk, [])
                        if tc_label not in order_list:
                            order_list.append(tc_label)
            except Exception:
                pass

    def get_field(self, name: str):
        """Look up a RulebookField by slug or display name (case-insensitive)."""
        lower = name.lower()
        return self._by_slug.get(lower) or self._by_name.get(lower)

    def get_group_label(self, field_pk: int, content_type_id: int) -> str:
        """Return the display label (str(TypeConfig)) for a content type in this field."""
        return self._ct_group_label.get((field_pk, content_type_id), "")

    def matches_type_hint(self, field_pk: int, content_type_id: int, hint: str) -> bool:
        """Return True if the given content type matches the type hint for this field."""
        classes = self._ct_classes.get((field_pk, content_type_id), set())
        lower_hint = hint.lower()
        # Direct match against matching_class (e.g. hint "zone" == matching_class "zone")
        if lower_hint in classes:
            return True
        # Plural tolerance: "zones" → try "zone"
        if lower_hint.endswith("s") and lower_hint[:-1] in classes:
            return True
        return False

    @property
    def facetable_fields(self) -> List:
        """All fields ordered by sort_order (matching table column order). Every field is facetable."""
        return sorted(
            self._by_slug.values(),
            key=lambda x: getattr(x, "sort_order", 9999),
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
    """Resolve a property name on a NetBox object or SecurityObjectGroup."""
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

    # --- generic attribute lookup — no fallback ---
    val = getattr(obj, sf, None)
    if val is None:
        return []
    if hasattr(val, "all"):  # ManyToMany / queryset
        return [str(v) for v in val.all()]
    return [str(val)]


def _parse_sub_field(sub_field: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Parse 'type_hint' or 'type_hint.prop' into (type_hint, prop).

    Returns (None, None) when sub_field is None/empty.
    Single segment → (type_hint, None) — prop defaults to 'name' in _get_sub_field_values.
    """
    if not sub_field:
        return None, None
    parts = sub_field.split(".", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0], None


def _get_field_values_with_group(
    rule, field, sub_field: Optional[str], context: Optional["RulebookContext"]
) -> List[Tuple[str, str]]:
    """Like _get_field_values but returns (value, group_label) pairs.

    group_label is str(TypeConfig) for object items; "" for group items.
    """
    results: List[Tuple[str, str]] = []
    field_pk = field.pk
    type_hint, prop = _parse_sub_field(sub_field)

    for item in getattr(rule, "_cached_object_items", []):
        if item.field_id != field_pk:
            continue
        if type_hint and context is not None:
            if not context.matches_type_hint(field_pk, item.content_type_id, type_hint):
                continue
        grp = context.get_group_label(field_pk, item.content_type_id) if context else ""
        for val in _get_sub_field_values(item.assigned_object, prop):
            results.append((val, grp))

    for item in getattr(rule, "_cached_group_items", []):
        if item.field_id != field_pk:
            continue
        for val in _get_sub_field_values(item.security_group, prop):
            results.append((val, ""))

    return results


def _get_field_values(rule, field, sub_field: Optional[str], context: Optional["RulebookContext"] = None) -> List[str]:
    """Collect all sub-field values for a RulebookField within a rule.

    sub_field structure (mirrors query x.y.z):
      None          → default (name) across all type configs
      "zone"        → type-hint: only items whose matching_class == "zone", property = name
      "zone.prefix" → type-hint "zone", property "prefix"
    """
    values: List[str] = []
    field_pk = field.pk
    type_hint, prop = _parse_sub_field(sub_field)

    for item in getattr(rule, "_cached_object_items", []):
        if item.field_id != field_pk:
            continue
        if type_hint and context is not None:
            if not context.matches_type_hint(field_pk, item.content_type_id, type_hint):
                continue
        values.extend(_get_sub_field_values(item.assigned_object, prop))

    for item in getattr(rule, "_cached_group_items", []):
        if item.field_id != field_pk:
            continue
        # Groups have no content_type — type_hint is not applied to group items
        values.extend(_get_sub_field_values(item.security_group, prop))

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

    values = _get_field_values(rule, rb_field, condition.sub_field, context)
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

    def _rule_matches(rule) -> bool:
        # OR of AND-groups: rule matches if any group fully matches
        for group in (query.groups or [query.conditions]):
            if all(_evaluate_condition(rule, cond, context) for cond in group):
                return True
        return False

    return [rule for rule in rules if _rule_matches(rule)]


def compute_facets(
    all_rules: List, context: RulebookContext, filtered_rules: List = None
) -> List[Dict]:
    """
    Compute facet entries grouped by TypeConfig.

    all_rules:      full rule set – determines which entries/groups are shown
    filtered_rules: currently active subset – determines displayed counts
                    (None = same as all_rules, i.e. no filter active)

    Each facet's entries_value / entries_set is a list of group-blocks:
        [{"group": "App › TypeName", "group_short": "TypeName", "entries": [...]}, ...]

    Entries carry {"value", "count", "disabled", "qval"}.
    disabled=True when count==0 in filtered_rules.
    """
    if filtered_rules is None:
        filtered_rules = all_rules

    facets = []

    # ── Fixed: Status facet (no type grouping) ───────────────────────────
    status_all: Counter = Counter()
    for rule in all_rules:
        status_all["Enabled" if getattr(rule, "enabled", True) else "Disabled"] += 1
    status_filt: Counter = Counter()
    for rule in filtered_rules:
        status_filt["Enabled" if getattr(rule, "enabled", True) else "Disabled"] += 1

    if status_all:
        status_entries = [
            {
                "value": val,
                "count": status_filt.get(val, 0),
                "disabled": status_filt.get(val, 0) == 0,
                "qval": 'Enabled == "true"' if val == "Enabled" else 'Enabled == "false"',
            }
            for val, _ in status_all.most_common()
        ]
        status_grouped = [{"group": "", "group_short": "", "entries": status_entries}]
        facets.append(
            {
                "field_slug": "_status",
                "field_name": "Status",
                "field_subtitle": "",
                "facet_mode": "value",
                "facet_weight": 9999,
                "entries": status_grouped,
                "entries_value": status_grouped,
                "entries_set": status_grouped,
            }
        )

    # ── Dynamic fields ───────────────────────────────────────────────────
    for field in context.facetable_fields:
        fp = re.sub(r'\s*\(.*?\)\s*$', '', field.name).strip().lower()  # field_path used in qval

        # ── Value mode: (group, value) counts ──
        group_all_v: Dict[str, Counter] = {}
        group_filt_v: Dict[str, Counter] = {}
        group_order_v: List[str] = list(context._field_group_order.get(field.pk, []))

        for rule in all_rules:
            seen: set = set()
            for val, grp in _get_field_values_with_group(rule, field, None, context):
                if grp not in group_order_v:
                    group_order_v.append(grp)
                group_all_v.setdefault(grp, Counter())
                k = (grp, val)
                if k not in seen:
                    group_all_v[grp][val] += 1
                    seen.add(k)

        if not group_all_v:
            continue

        for rule in filtered_rules:
            seen = set()
            for val, grp in _get_field_values_with_group(rule, field, None, context):
                group_filt_v.setdefault(grp, Counter())
                k = (grp, val)
                if k not in seen:
                    group_filt_v[grp][val] += 1
                    seen.add(k)

        entries_value: List[Dict] = []
        for grp in group_order_v:
            all_c = group_all_v.get(grp, Counter())
            filt_c = group_filt_v.get(grp, Counter())
            grp_entries = []
            for val, all_count in all_c.most_common(500):
                cnt = filt_c.get(val, 0)
                grp_entries.append({
                    "value": val, "count": cnt, "count_all": all_count, "disabled": cnt == 0,
                    "qval": f'{fp} == "{val}"',
                })
            if grp_entries:
                grp_short = grp.split("›")[-1].strip() if "›" in grp else grp
                entries_value.append({"group": grp, "group_short": grp_short, "entries": grp_entries})

        # ── Set mode: group by (combination of) TypeConfigs ──
        group_all_s: Dict[str, Counter] = {}
        group_filt_s: Dict[str, Counter] = {}
        group_order_s: List[str] = []

        def _process_rule_set(rule, counter_dict: Dict[str, Counter]) -> Optional[str]:
            vg = _get_field_values_with_group(rule, field, None, context)
            by_group: Dict[str, set] = {}
            for val, grp in vg:
                by_group.setdefault(grp, set()).add(val)
            if not by_group:
                return None
            if len(by_group) == 1:
                grp = next(iter(by_group))
                set_key = ", ".join(sorted(by_group[grp]))
                grp_label = grp.split("›")[-1].strip() if "›" in grp else grp
            else:
                sorted_grps = sorted(by_group.keys())
                shorts = [g.split("›")[-1].strip() if "›" in g else g for g in sorted_grps]
                grp_label = " + ".join(shorts)
                set_key = ", ".join(sorted(v for vals in by_group.values() for v in vals))
            counter_dict.setdefault(grp_label, Counter())
            counter_dict[grp_label][set_key] += 1
            return grp_label

        for rule in all_rules:
            lbl = _process_rule_set(rule, group_all_s)
            if lbl and lbl not in group_order_s:
                group_order_s.append(lbl)
        for rule in filtered_rules:
            _process_rule_set(rule, group_filt_s)

        entries_set: List[Dict] = []
        for grp in group_order_s:
            all_c = group_all_s.get(grp, Counter())
            filt_c = group_filt_s.get(grp, Counter())
            grp_entries = []
            for val, _ in all_c.most_common(500):
                cnt = filt_c.get(val, 0)
                all_count = all_c[val]
                parts = [v.strip() for v in val.split(",") if v.strip()]
                if len(parts) == 1:
                    qval = f'{fp} == "{parts[0]}"'
                else:
                    qval = f'{fp} in ({", ".join(parts)})'
                grp_entries.append({"value": val, "count": cnt, "count_all": all_count, "disabled": cnt == 0, "qval": qval})
            if grp_entries:
                entries_set.append({"group": grp, "group_short": grp, "entries": grp_entries})

        # Subtitle: distinct short TypeConfig names (strip app prefix)
        type_names = list(
            dict.fromkeys(
                (str(ft.type_config).split("\u203a")[-1].strip() if "\u203a" in str(ft.type_config) else str(ft.type_config))
                for ft in sorted(field.type_configs.all(), key=lambda ft: ft.sort_order)
            )
        )
        subtitle = ", ".join(type_names) if type_names else ""

        facets.append(
            {
                "field_slug": field.slug,
                "field_name": re.sub(r'\s*\(.*?\)\s*$', '', field.name).strip(),
                "field_subtitle": subtitle,
                "facet_mode": getattr(field, "facet_mode", "value"),
                "facet_weight": getattr(field, "facet_weight", 100),
                "entries": entries_value,
                "entries_value": entries_value,
                "entries_set": entries_set,
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
