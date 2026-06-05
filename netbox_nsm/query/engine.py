"""
NSM Query Engine

Evaluates parsed Query objects against Rule instances.
Also computes Facets from the result set.

Design principles:
- Generic field resolution — no hard-coded field names.
- All filtering goes through this engine (policy view, global search, API).
- Rules must be pre-loaded with cached_object_items / cached_group_items.
"""

import ipaddress
import re
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

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
                fields_qs = rulebook.fields.prefetch_related(
                    "type_configs__type_config__content_type"
                ).all()
                for f in fields_qs:
                    self._by_slug[f.slug.lower()] = f
                    self._by_name[f.name.lower()] = f
            except Exception:
                pass

        self._type_keys_by_field: Dict[int, Dict[str, int]] = {}
        for f in self._by_slug.values():
            self._type_keys_by_field[f.pk] = self._build_type_key_map(f)

    def _build_type_key_map(self, field) -> Dict[str, int]:
        """Map normalized type segment aliases to content_type_id for a field."""
        key_map: Dict[str, int] = {}
        for ft in field.type_configs.all():
            tc = ft.type_config
            ct = tc.content_type
            ct_id = ct.id
            candidates = [
                tc.name,
                tc.matching_class,
                ct.model,
                ct.model.replace("_", " "),
                ct.model.replace("_", "-"),
            ]
            if ct.model.startswith("nsm_"):
                candidates.append(ct.model[4:])
            for raw in candidates:
                key = _segment_key(raw)
                if key:
                    key_map[key] = ct_id
        return key_map

    def resolve_type_content_type_id(self, field, type_segment: str) -> Optional[int]:
        """Return content_type_id for a type segment within a rulebook field."""
        if not type_segment:
            return None
        key_map = self._type_keys_by_field.get(field.pk, {})
        return key_map.get(_segment_key(type_segment))

    def get_field(self, name: str):
        """Look up a RulebookField by slug or display name (case-insensitive)."""
        lower = name.lower()
        return self._by_slug.get(lower) or self._by_name.get(lower)

    @property
    def filter_panel_fields(self) -> List:
        """Visible object columns shown in the policy filter sidebar."""
        return sorted(
            (
                f
                for f in self._by_slug.values()
                if not getattr(f, "is_system_field", False)
                and getattr(f, "visible", True)
            ),
            key=lambda x: (-getattr(x, "facet_weight", 100), x.slug),
        )

    @property
    def facetable_fields(self) -> List:
        """Object fields shown as facet cards in the policy filter panel."""
        return sorted(
            (
                f
                for f in self._by_slug.values()
                if not getattr(f, "is_system_field", False)
                and getattr(f, "visible", True)
                and getattr(f, "facet_mode", "value") != "disabled"
            ),
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
    "index": "index",
    "rule.index": "index",
    "enabled": "enabled",
    "status": "enabled",
    "rule.enabled": "enabled",
    "rule.status": "enabled",
}


def _segment_key(value: str) -> str:
    return re.sub(r"[\s\-_.]+", "", (value or "").lower())


def _object_attribute(obj, attr: str):
    """Read an attribute from a NetBox or custom object, including field_data."""
    if obj is None or not attr:
        return None
    val = getattr(obj, attr, None)
    if val not in (None, ""):
        return val
    fd = getattr(obj, "field_data", None)
    if isinstance(fd, dict) and attr in fd:
        raw = fd[attr]
        if isinstance(raw, dict):
            return raw.get("str") or raw.get("display") or raw.get("value")
        return raw
    return None


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
    """Resolve sub_field (z) on a NetBox object or ObjectGroup."""
    if obj is None:
        return []

    sf = (sub_field or "name").lower()

    # --- name / labels ---
    if sf in ("name", "label", "labels"):
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
        name_val = _object_attribute(obj, "name")
        if name_val not in (None, ""):
            return [str(name_val)]
        return [str(obj)]

    # --- address / prefix ---
    if sf in ("address", "prefix", "ip", "network", "ip_address"):
        for attr_name in ("address", "prefix", "host", "ip_address"):
            val = _object_attribute(obj, attr_name)
            if val not in (None, ""):
                return [str(val)]
        return []

    # --- generic attribute / field_data lookup ---
    val = _object_attribute(obj, sf)
    if val is None:
        return []
    if hasattr(val, "all"):  # ManyToMany / queryset
        return [str(v) for v in val.all()]
    if isinstance(val, (list, tuple)):
        return [str(v) for v in val if v not in (None, "")]
    return [str(val)]


def _group_matches_type_segment(type_segment: str) -> bool:
    return _segment_key(type_segment) in {"group", "groups"}


def _get_field_values(
    rule,
    field,
    sub_field: Optional[str],
    *,
    type_segment: Optional[str] = None,
    context: Optional[RulebookContext] = None,
) -> List[str]:
    """Collect sub-field values for a RulebookField within a rule."""
    from netbox_nsm.display_utils import get_display_template_map, render_object_display

    values: List[str] = []
    field_pk = field.pk
    type_ct_id = None
    if type_segment and context is not None:
        type_ct_id = context.resolve_type_content_type_id(field, type_segment)

    resolve_name = (sub_field or "name").lower() == "name"
    tmpl_map = get_display_template_map() if resolve_name else None

    for item in getattr(rule, "_cached_object_items", []):
        if item.field_id != field_pk:
            continue
        if type_ct_id is not None and item.content_type_id != type_ct_id:
            continue
        obj = item.assigned_object
        if obj is None:
            continue
        if resolve_name:
            label = render_object_display(obj, item.content_type_id, tmpl_map)
            if label:
                values.append(label)
        else:
            values.extend(_get_sub_field_values(obj, sub_field))

    if type_ct_id is None or _group_matches_type_segment(type_segment or ""):
        for item in getattr(rule, "_cached_group_items", []):
            if item.field_id != field_pk:
                continue
            grp = item.security_group
            if grp is None:
                continue
            if resolve_name:
                label = str(getattr(grp, "name", None) or grp)
                if label:
                    values.append(label)
            else:
                values.extend(_get_sub_field_values(grp, sub_field))

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


def _resolve_object_condition(
    condition: Condition, context: RulebookContext, rb_field
) -> Condition:
    """Map two-part x.y paths onto x.y.z when y matches a type column."""
    if condition.type_segment or not condition.sub_field:
        return condition

    if context.resolve_type_content_type_id(rb_field, condition.sub_field) is None:
        if not _group_matches_type_segment(condition.sub_field):
            return condition

    if condition.operator in ("exists", "!exists"):
        return Condition(
            field=condition.field,
            type_segment=condition.sub_field,
            sub_field=None,
            operator=condition.operator,
            value=condition.value,
        )

    return Condition(
        field=condition.field,
        type_segment=condition.sub_field,
        sub_field="name",
        operator=condition.operator,
        value=condition.value,
    )


def _evaluate_condition(rule, condition: Condition, context: RulebookContext) -> bool:
    """Evaluate a single Condition against a rule."""
    fixed_val = _get_fixed_value(rule, condition.field_path())
    if fixed_val is None and not condition.type_segment:
        fixed_val = _get_fixed_value(rule, condition.field)

    if fixed_val is not None:
        return _apply_operator([fixed_val], condition.operator, condition.value)

    rb_field = context.get_field(condition.field)
    if rb_field is None:
        return False

    condition = _resolve_object_condition(condition, context, rb_field)

    if condition.type_segment and context.resolve_type_content_type_id(
        rb_field, condition.type_segment
    ) is None and not _group_matches_type_segment(condition.type_segment):
        return False

    values = _get_field_values(
        rule,
        rb_field,
        condition.sub_field,
        type_segment=condition.type_segment,
        context=context,
    )
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

    if query.or_groups:
        return [
            rule
            for rule in rules
            if any(
                all(_evaluate_condition(rule, cond, context) for cond in group)
                for group in query.or_groups
            )
        ]

    return [
        rule
        for rule in rules
        if all(_evaluate_condition(rule, cond, context) for cond in query.conditions)
    ]


def _count_status_facets(rules: List) -> Counter:
    status_counts: Counter = Counter()
    for rule in rules:
        status_counts["Enabled" if getattr(rule, "enabled", True) else "Disabled"] += 1
    return status_counts


def _count_name_facets(rules: List) -> Counter:
    counter: Counter = Counter()
    for rule in rules:
        if rule.name:
            counter[rule.name] += 1
    return counter


def _system_field_visible(context: RulebookContext, slug: str) -> bool:
    field = context._by_slug.get(slug)
    if field is None or not getattr(field, "is_system_field", False):
        return False
    return getattr(field, "visible", True) and getattr(field, "filterable", True)


def _system_field_facet_visible(context: RulebookContext, slug: str) -> bool:
    """System column shown in facet sidebar (visibility only, not filterable flag)."""
    field = context._by_slug.get(slug)
    if field is None or not getattr(field, "is_system_field", False):
        return False
    return getattr(field, "visible", True)


def _count_field_facets(rules: List, context: RulebookContext):
    """Yield (field, counter_value, counter_set) for each facetable field."""
    for field in context.facetable_fields:
        counter_value: Counter = Counter()
        counter_set: Counter = Counter()

        for rule in rules:
            values = _get_field_values(rule, field, "name")
            for v in set(values):
                counter_value[v] += 1
            if values:
                key = ", ".join(sorted(set(values)))
                counter_set[key] += 1

        if counter_value:
            yield field, counter_value, counter_set


def _make_facet_entries(
    counter_all: Counter,
    counter_filtered: Counter,
    *,
    field_path: str,
    filter_field: str,
    query: Optional[Query],
    limit: int = 100,
    qval_for: Optional[Callable[[str], str]] = None,
) -> List[Dict]:
    from .parser import (
        query_and_condition,
        query_has_condition,
        query_replace_all,
    )

    if qval_for is None:
        qval_for = lambda val: f'{field_path} = "{val}"'

    query_active = query is not None and query.is_active
    all_keys = set(counter_all.keys()) | set(counter_filtered.keys())
    sorted_keys = sorted(
        all_keys,
        key=lambda k: (-counter_all.get(k, 0), str(k).lower()),
    )[:limit]

    entries = []
    for val in sorted_keys:
        count_all = counter_all.get(val, 0)
        count_filtered = counter_filtered.get(val, 0)
        qval = qval_for(val)
        active = query_has_condition(query, qval) if query_active else False
        available = (not query_active) or count_filtered > 0 or active
        if available:
            href = (
                qval
                if not query_active
                else query_and_condition(query, qval)
            )
        else:
            href = query_replace_all(qval)
        entries.append(
            {
                "value": val,
                "count": count_filtered if available else count_all,
                "count_all": count_all,
                "count_filtered": count_filtered,
                "available": available,
                "qval": qval,
                "href": href,
                "active": active,
            }
        )
    return entries


def _make_status_entries(
    counter_all: Counter,
    counter_filtered: Counter,
    *,
    query: Optional[Query],
) -> List[Dict]:
    def qval_for(val: str) -> str:
        return 'Enabled == "true"' if val == "Enabled" else 'Enabled == "false"'

    return _make_facet_entries(
        counter_all,
        counter_filtered,
        field_path="Enabled",
        filter_field="Enabled",
        query=query,
        limit=10,
        qval_for=qval_for,
    )


def _make_name_entries(
    counter_all: Counter,
    counter_filtered: Counter,
    *,
    query: Optional[Query],
) -> List[Dict]:
    return _make_facet_entries(
        counter_all,
        counter_filtered,
        field_path="name",
        filter_field="name",
        query=query,
        limit=100,
    )


def compute_facets(
    filtered_rules: List,
    context: RulebookContext,
    *,
    all_rules: Optional[List] = None,
    query: Optional[Query] = None,
) -> List[Dict]:
    """
    Compute facet entries for the policy sidebar.

    When `all_rules` and `query` are provided, entries that no longer match the
    active filter are marked unavailable (grayed) and show counts from the full
    rule set. Available entries append with AND on click; unavailable entries
    replace the entire active filter.
    """
    if all_rules is None:
        all_rules = filtered_rules

    facets = []

    status_all = _count_status_facets(all_rules)
    status_filtered = _count_status_facets(filtered_rules)
    if _system_field_facet_visible(context, "status"):
        if not status_all:
            status_all = Counter({"Enabled": 0, "Disabled": 0})
        status_entries = _make_status_entries(
            status_all, status_filtered, query=query
        )
        facets.append(
            {
                "field_slug": "_status",
                "field_name": "Status",
                "field_subtitle": "",
                "facet_mode": "value",
                "facet_weight": 9999,
                "entries": status_entries,
                "entries_value": status_entries,
                "entries_set": status_entries,
            }
        )

    if _system_field_visible(context, "name"):
        name_all = _count_name_facets(all_rules)
        name_filtered = _count_name_facets(filtered_rules)
        if name_all:
            name_field = context.get_field("name")
            name_entries = _make_name_entries(name_all, name_filtered, query=query)
            facets.append(
                {
                    "field_slug": "_name",
                    "field_name": name_field.name if name_field else "Name",
                    "field_subtitle": "",
                    "facet_mode": "value",
                    "facet_weight": 9500,
                    "entries": name_entries,
                    "entries_value": name_entries,
                    "entries_set": name_entries,
                }
            )

    all_by_slug = {
        field.slug: (field, cv, cs)
        for field, cv, cs in _count_field_facets(all_rules, context)
    }
    filtered_by_slug = {
        field.slug: (field, cv, cs)
        for field, cv, cs in _count_field_facets(filtered_rules, context)
    }

    for slug in all_by_slug:
        field, counter_value_all, counter_set_all = all_by_slug[slug]
        _, counter_value_filtered, counter_set_filtered = filtered_by_slug.get(
            slug, (field, Counter(), Counter())
        )
        field_path = f"{field.slug.lower()}.name"

        type_names = list(
            dict.fromkeys(
                str(ft.type_config)
                for ft in sorted(field.type_configs.all(), key=lambda ft: ft.sort_order)
                if ft.visible
            )
        )
        subtitle = ", ".join(type_names) if type_names else ""

        entries_value = _make_facet_entries(
            counter_value_all,
            counter_value_filtered,
            field_path=field_path,
            filter_field=field.name,
            query=query,
        )
        entries_set = _make_facet_entries(
            counter_set_all,
            counter_set_filtered,
            field_path=field_path,
            filter_field=field.name,
            query=query,
        )

        facets.append(
            {
                "field_slug": field.slug,
                "field_name": field.name,
                "field_subtitle": subtitle,
                "facet_mode": getattr(field, "facet_mode", "value"),
                "facet_weight": getattr(field, "facet_weight", 100),
                "entries": entries_value,
                "entries_value": entries_value,
                "entries_set": entries_set,
            }
        )

    present_slugs = {f["field_slug"] for f in facets}
    for field in context.facetable_fields:
        if field.slug in present_slugs:
            continue
        type_names = list(
            dict.fromkeys(
                str(ft.type_config)
                for ft in sorted(field.type_configs.all(), key=lambda ft: ft.sort_order)
                if ft.visible
            )
        )
        subtitle = ", ".join(type_names) if type_names else ""
        facets.append(
            {
                "field_slug": field.slug,
                "field_name": field.name,
                "field_subtitle": subtitle,
                "facet_mode": getattr(field, "facet_mode", "value"),
                "facet_weight": getattr(field, "facet_weight", 100),
                "entries": [],
                "entries_value": [],
                "entries_set": [],
            }
        )

    facets.sort(key=lambda f: -f.get("facet_weight", 0))
    return facets


# ---------------------------------------------------------------------------
# Query help — dynamic x.y.z examples for the policy UI
# ---------------------------------------------------------------------------

_TYPE_PROPERTY_HINTS: Dict[str, List[str]] = {
    "address": ["name", "prefix", "ip_address"],
    "zone": ["name"],
    "service": ["name", "protocol", "port"],
    "action": ["name"],
    "label": ["name"],
    "label-scope": ["name"],
    "group": ["name"],
}


def type_search_properties(type_config) -> List[str]:
    mc = getattr(type_config, "matching_class", "") or ""
    return list(_TYPE_PROPERTY_HINTS.get(mc, ["name"]))


def type_segment_slug(type_config) -> str:
    """Preferred lowercase y-segment for query paths."""
    name_key = _segment_key(type_config.name)
    if name_key:
        return name_key
    mc = _segment_key(type_config.matching_class or "")
    if mc:
        return mc
    model = type_config.content_type.model
    if model.startswith("nsm_"):
        return model[4:].replace("_", "")
    return model.replace("_", "")


def build_query_help_sections(rulebook) -> List[Dict]:
    """Build rulebook-specific x.y.z query help for the policy search UI."""
    from netbox_nsm.models import RulebookFieldKind

    sections: List[Dict] = []
    for field in rulebook.fields.filter(
        field_kind=RulebookFieldKind.OBJECT,
        filterable=True,
    ).prefetch_related("type_configs__type_config__content_type"):
        types = []
        for ft in sorted(field.type_configs.all(), key=lambda x: x.sort_order):
            if not ft.visible:
                continue
            tc = ft.type_config
            types.append(
                {
                    "name": tc.name,
                    "slug": type_segment_slug(tc),
                    "properties": type_search_properties(tc),
                }
            )
        if types:
            sections.append(
                {
                    "field_slug": field.slug.lower(),
                    "field_name": field.name,
                    "types": types,
                }
            )
    return sections


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
                    "plugins:netbox_nsm:rulebook_rules",
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
