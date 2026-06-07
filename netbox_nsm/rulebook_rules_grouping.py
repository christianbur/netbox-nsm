"""Group policy rules by object column or field tags."""

from __future__ import annotations

from collections import defaultdict

from django.utils.translation import gettext_lazy as _

from netbox_nsm.models import Rulebook
from netbox_nsm.rule_field_selections import parse_rules_column_key

__all__ = (
    "COLLAPSE_ALL",
    "EXPAND_ALL",
    "GROUP_BY_RULEBOOK",
    "GROUP_BY_NOT_ALLOWED_MESSAGE",
    "GROUP_DUPLICATE_MESSAGE",
    "GROUP_MAIN_LEVEL_LABEL",
    "GROUP_MAX_MESSAGE",
    "TABLE_DRAG_DISABLED_MESSAGE",
    "GROUP_SUBGROUP_LEVEL_LABEL",
    "GROUP_MODE_SET",
    "GROUP_MODE_VALUE",
    "UNGROUPED_GROUP_KEY",
    "assign_rules_to_groups",
    "build_rulebook_rules_group_options",
    "build_rule_display_items",
    "filter_collapsed_display_items",
    "filter_group_display_items",
    "group_by_field_label",
    "parse_collapsed_keys",
    "parse_expanded_keys",
    "parse_group_by_mode",
    "parse_rulebook_rules_group_modes",
    "parse_group_default_expanded",
    "parse_rulebook_rules_group_by",
    "parse_rulebook_rules_group_levels",
    "rules_grouping_enabled",
    "resolve_group_by_value",
    "assign_rules_to_groups_for_union",
    "RULES_GROUP_MAX_LEVELS",
    "resolve_group_expansion",
    "resolve_group_expansion_for_rules",
    "resolve_request_group_expansion",
    "validate_rulebook_rules_group_request",
)

GROUP_BY_QUERY_PARAMS = ("group_by", "group_by_2", "group_by_3")
GROUP_BY_NOT_ALLOWED_MESSAGE = _("Field is not configured for this rulebook.")
GROUP_MAX_MESSAGE = _("Maximum of two columns allowed for grouping.")
GROUP_DUPLICATE_MESSAGE = _("This column is already in the grouping.")
TABLE_DRAG_DISABLED_MESSAGE = _(
    "Switch to Group or Matrix view to organize rules by drag-and-drop."
)
GROUP_MAIN_LEVEL_LABEL = _("Main group")
GROUP_SUBGROUP_LEVEL_LABEL = _("Subgroup")

UNGROUPED_GROUP_KEY = "__ungrouped__"
COLLAPSE_ALL = "__all__"
EXPAND_ALL = "__all__"
GROUP_BY_RULEBOOK = "rulebook"
GROUP_MODE_VALUE = "value"
GROUP_MODE_SET = "set"
RULES_GROUP_MAX_LEVELS = 2
UNGROUPED_LABEL = _("Ungrouped")


class PolicyGroupBucket(dict):
    """Group header payload: key, label, url, color."""

    pass


def build_rulebook_rules_group_options(
    rules_layout: list,
    *,
    include_rulebook: bool = False,
) -> list[dict]:
    """Dropdown options: none, tag per object field, each object column."""
    options: list[dict] = [{"value": "", "label": str(_("None"))}]
    if include_rulebook:
        options.append(
            {
                "value": GROUP_BY_RULEBOOK,
                "label": str(_("Rulebook")),
            }
        )
    for entry in rules_layout or []:
        if entry.get("kind") != "object":
            continue
        field_slug = entry.get("slug") or ""
        field_label = entry.get("label") or field_slug
        options.append(
            {
                "value": f"tag:{field_slug}",
                "label": f"{field_label} — {_('Tag')}",
            }
        )
        for col in (entry.get("group") or {}).get("columns") or []:
            col_key = col.get("key") or ""
            col_label = col.get("label") or col_key
            options.append(
                {
                    "value": f"col:{col_key}",
                    "label": f"{field_label} / {col_label}",
                }
            )
    return options


def allowed_group_by_values(
    rules_layout: list,
    *,
    include_rulebook: bool = False,
) -> set[str]:
    return {
        opt["value"]
        for opt in build_rulebook_rules_group_options(
            rules_layout,
            include_rulebook=include_rulebook,
        )
        if opt.get("value")
    }


def validate_rulebook_rules_group_request(
    request,
    *,
    rules_layout: list | None = None,
    include_rulebook: bool = False,
) -> str | None:
    """Return a user-facing error when group_by URL params are not allowed."""
    if rules_layout is None:
        return None
    for param in GROUP_BY_QUERY_PARAMS:
        raw = (request.GET.get(param) or "").strip()
        if not raw:
            continue
        resolved = resolve_group_by_value(
            raw,
            rules_layout,
            include_rulebook=include_rulebook,
        )
        if not resolved:
            return str(GROUP_BY_NOT_ALLOWED_MESSAGE)
    return None


def group_by_field_label(mode: str, rules_layout: list | None = None) -> str:
    """Human label for the active group-by dimension (auto-group-column hint)."""
    if mode == GROUP_BY_RULEBOOK:
        return str(_("Rulebook"))
    for opt in build_rulebook_rules_group_options(rules_layout or []):
        if opt.get("value") == mode:
            return str(opt.get("label") or mode)
    return mode


def _normalize_group_by_value(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if raw == GROUP_BY_RULEBOOK:
        return GROUP_BY_RULEBOOK
    if raw.startswith("col:") or raw.startswith("tag:"):
        return raw
    return ""


def _is_union_column_key(column_key: str) -> bool:
    """True for all-rules union keys (Area::TypeLabel), not policy keys (slug::ct_N)."""
    if "::" not in column_key:
        return False
    _area, type_part = column_key.split("::", 1)
    return not type_part.startswith("ct_")


def _resolve_column_group_alias(alias_key: str, rules_layout: list) -> str:
    """Map legacy col:AreaLabel::ColumnLabel to the canonical column key."""
    if "::" not in alias_key:
        return ""
    area_part, col_part = alias_key.split("::", 1)
    area_lower = area_part.lower()
    col_lower = col_part.lower()
    for entry in rules_layout or []:
        if entry.get("kind") != "object":
            continue
        area_label = (entry.get("label") or "").strip()
        area_slug = (entry.get("slug") or "").strip()
        if area_lower not in {area_label.lower(), area_slug.lower()}:
            continue
        for col in (entry.get("group") or {}).get("columns") or []:
            col_key = (col.get("key") or "").strip()
            col_label = (col.get("label") or "").strip()
            if col_key == alias_key:
                return col_key
            if col_label.lower() == col_lower:
                return col_key
    return ""


def resolve_group_by_value(
    raw: str,
    rules_layout: list,
    *,
    include_rulebook: bool = False,
) -> str:
    """Return canonical group_by value, resolving legacy area/header aliases."""
    normalized = _normalize_group_by_value(raw)
    if not normalized:
        return ""
    allowed = allowed_group_by_values(
        rules_layout or [],
        include_rulebook=include_rulebook,
    )
    if normalized in allowed:
        return normalized
    if normalized.startswith("col:"):
        alias_key = normalized[4:]
        if _is_union_column_key(alias_key):
            resolved = _resolve_column_group_alias(alias_key, rules_layout)
            if resolved:
                canonical = f"col:{resolved}"
                if canonical in allowed:
                    return canonical
            if normalized in allowed:
                return normalized
        else:
            resolved = _resolve_column_group_alias(alias_key, rules_layout)
            if resolved:
                canonical = f"col:{resolved}"
                if canonical in allowed:
                    return canonical
    return ""


def parse_rulebook_rules_group_by(
    request,
    *,
    rules_layout: list | None = None,
    include_rulebook: bool = False,
) -> str:
    raw = (request.GET.get("group_by") or "").strip()
    if not raw:
        return ""
    if rules_layout is None:
        normalized = _normalize_group_by_value(raw)
        return normalized
    return resolve_group_by_value(
        raw,
        rules_layout,
        include_rulebook=include_rulebook,
    )


def parse_rulebook_rules_group_levels(
    request,
    *,
    rules_layout: list | None = None,
    include_rulebook: bool = False,
) -> list[str]:
    """Primary and optional secondary group dimensions (multi-level grouping)."""
    primary = parse_rulebook_rules_group_by(
        request,
        rules_layout=rules_layout,
        include_rulebook=include_rulebook,
    )
    if not primary:
        return []
    secondary_raw = (request.GET.get("group_by_2") or "").strip()
    if not secondary_raw:
        return [primary][:RULES_GROUP_MAX_LEVELS]
    if rules_layout is None:
        secondary = _normalize_group_by_value(secondary_raw)
    else:
        secondary = resolve_group_by_value(
            secondary_raw,
            rules_layout,
            include_rulebook=include_rulebook,
        )
    if secondary and secondary != primary:
        return [primary, secondary][:RULES_GROUP_MAX_LEVELS]
    return [primary][:RULES_GROUP_MAX_LEVELS]


def rules_grouping_enabled(request, *, rules_layout: list | None = None) -> bool:
    return bool(parse_rulebook_rules_group_by(request, rules_layout=rules_layout))


def parse_group_by_mode(request, *, param: str = "group_mode") -> str:
    """Always group by full cell content (set mode). Legacy group_mode URL params are ignored."""
    del request, param
    return GROUP_MODE_SET


def parse_rulebook_rules_group_modes(request) -> tuple[str, str]:
    """Primary and secondary grouping modes (both fixed to set / full cell content)."""
    del request
    return GROUP_MODE_SET, GROUP_MODE_SET


def parse_collapsed_keys(raw: str | None) -> set[str]:
    if not raw:
        return set()
    parts = {part.strip() for part in str(raw).split(",") if part.strip()}
    if not parts:
        return set()
    lowered = {part.lower() for part in parts}
    if "all" in lowered or "*" in parts:
        return {COLLAPSE_ALL}
    return parts


def parse_expanded_keys(raw: str | None) -> set[str] | None:
    if not raw:
        return set()
    parts = {part.strip() for part in str(raw).split(",") if part.strip()}
    if not parts:
        return set()
    lowered = {part.lower() for part in parts}
    if "all" in lowered or "*" in parts:
        return {EXPAND_ALL}
    return parts


def parse_group_default_expanded(request) -> int:
    """Nested group expand default: 0, 1, or -1."""
    raw = (request.GET.get("group_expanded") or "").strip()
    if not raw:
        return 0
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    if value < 0:
        return -1
    return max(0, value)


def resolve_group_expansion(
    request,
    *,
    group_by: str,
    display_items: list[dict] | None = None,
) -> tuple[set[str] | None, set[str] | None, int | None]:
    """Return (expanded_keys, collapsed_keys, default_expanded_level).

    default_expanded_level mirrors nested group expand when no explicit
    expanded/collapsed URL params are present.
    """
    if not group_by:
        return None, None, None
    if "expanded" in request.GET:
        return parse_expanded_keys(request.GET.get("expanded")), None, None
    collapsed_raw = request.GET.get("collapsed")
    if collapsed_raw:
        return None, parse_collapsed_keys(collapsed_raw), None
    default_level = parse_group_default_expanded(request)
    if default_level == 0:
        return None, {COLLAPSE_ALL}, None
    if default_level < 0:
        return {EXPAND_ALL}, None, None
    if display_items:
        level_keys = _group_keys_for_level(display_items, default_level)
        if level_keys:
            return level_keys, None, default_level
    return None, {COLLAPSE_ALL}, default_level


def _group_keys_for_level(display_items: list[dict], level: int) -> set[str]:
    keys: set[str] = set()
    for item in display_items:
        if item.get("kind") != "group":
            continue
        item_level = int(item.get("group_level") or 1)
        if item_level <= level:
            key = item.get("group_key")
            if key:
                keys.add(str(key))
    return keys


def _group_ancestor_keys(group_key: str) -> list[str]:
    if not group_key or group_key == UNGROUPED_GROUP_KEY:
        return [group_key] if group_key else []
    if "::" not in group_key:
        return [group_key]
    parts = group_key.split("::")
    return ["::".join(parts[: idx + 1]) for idx in range(len(parts))]


def _is_group_chain_expanded(
    group_key: str,
    *,
    expanded_keys: set[str] | None,
    collapsed_keys: set[str] | None,
) -> bool:
    if expanded_keys is not None:
        if EXPAND_ALL in expanded_keys:
            return True
        for ancestor in _group_ancestor_keys(group_key):
            if ancestor in expanded_keys:
                return True
        return False
    if not collapsed_keys:
        return True
    if COLLAPSE_ALL in collapsed_keys:
        return False
    for ancestor in _group_ancestor_keys(group_key):
        if ancestor in collapsed_keys:
            return False
    return True


def _is_nested_group_header_visible(
    item: dict,
    *,
    expanded_keys: set[str] | None,
    collapsed_keys: set[str] | None,
) -> bool:
    group_key = str(item.get("group_key") or "")
    group_level = int(item.get("group_level") or 1)
    if group_level == 1:
        return True
    parent_key = item.get("parent_key")
    if expanded_keys is not None:
        if EXPAND_ALL in expanded_keys:
            return True
        if group_key in expanded_keys:
            return True
        if parent_key and str(parent_key) in expanded_keys:
            return True
        return False
    if collapsed_keys is not None:
        if COLLAPSE_ALL in collapsed_keys:
            return False
        parent_key = item.get("parent_key")
        if parent_key and str(parent_key) in collapsed_keys:
            return False
        return True
    return True


def _is_nested_rule_visible(
    item: dict,
    *,
    expanded_keys: set[str] | None,
    collapsed_keys: set[str] | None,
) -> bool:
    group_key = str(item.get("group_key") or "")
    group_level = int(item.get("group_level") or 1)
    if group_level <= 1:
        if expanded_keys is not None:
            if EXPAND_ALL in expanded_keys:
                return True
            return group_key in expanded_keys
        if collapsed_keys is not None:
            if COLLAPSE_ALL in collapsed_keys:
                return False
            return group_key not in collapsed_keys
        return True
    if expanded_keys is not None:
        if EXPAND_ALL in expanded_keys:
            return True
        return group_key in expanded_keys
    if collapsed_keys is not None:
        if COLLAPSE_ALL in collapsed_keys:
            return False
        return _is_group_chain_expanded(
            group_key,
            expanded_keys=None,
            collapsed_keys=collapsed_keys,
        )
    return True


def _is_display_item_visible(
    item: dict,
    *,
    expanded_keys: set[str] | None = None,
    collapsed_keys: set[str] | None = None,
) -> bool:
    kind = item.get("kind")
    if kind == "group":
        return _is_nested_group_header_visible(
            item,
            expanded_keys=expanded_keys,
            collapsed_keys=collapsed_keys,
        )
    if kind == "rule":
        return _is_nested_rule_visible(
            item,
            expanded_keys=expanded_keys,
            collapsed_keys=collapsed_keys,
        )
    return True


def filter_group_display_items(
    display_items: list[dict],
    *,
    expanded_keys: set[str] | None = None,
    collapsed_keys: set[str] | None = None,
) -> list[dict]:
    if expanded_keys is not None:
        if EXPAND_ALL in expanded_keys:
            return display_items
        return [
            item
            for item in display_items
            if _is_display_item_visible(
                item,
                expanded_keys=expanded_keys,
                collapsed_keys=None,
            )
        ]
    if not collapsed_keys:
        return display_items
    if COLLAPSE_ALL in collapsed_keys:
        return [
            item
            for item in display_items
            if item.get("kind") == "group" and int(item.get("group_level") or 1) == 1
        ]
    return [
        item
        for item in display_items
        if _is_display_item_visible(
            item,
            expanded_keys=None,
            collapsed_keys=collapsed_keys,
        )
    ]


def _object_display_name(obj, content_type_id: int, tmpl_map) -> str:
    from netbox_nsm.display_utils import render_object_display

    try:
        label = render_object_display(obj, content_type_id, tmpl_map)
        if label:
            return str(label)
    except Exception:
        pass
    return str(getattr(obj, "name", None) or obj)


def _bucket(
    key: str,
    label: str,
    *,
    url: str = "#",
    color: str | None = None,
) -> PolicyGroupBucket:
    return PolicyGroupBucket(
        key=key,
        label=label,
        url=url,
        color=color,
    )


def _dedupe_buckets(buckets: list[PolicyGroupBucket]) -> list[PolicyGroupBucket]:
    deduped: dict[str, PolicyGroupBucket] = {}
    for bucket in buckets:
        deduped[bucket["key"]] = bucket
    return list(deduped.values())


def _set_bucket_label(labels: list[str]) -> str:
    """Display label for set-mode groups: one line per distinct zone/value."""
    return "\n".join(sorted({label for label in labels if label}, key=str.lower))


def _set_bucket_key(prefix: str, labels: list[str]) -> str:
    normalized = sorted({(label or "").lower() for label in labels if label})
    if not normalized:
        return ""
    return f"{prefix}::set::{'|'.join(normalized)}"


def _collapse_buckets(
    buckets: list[PolicyGroupBucket],
    *,
    key_prefix: str,
    group_mode: str,
) -> list[PolicyGroupBucket]:
    buckets = _dedupe_buckets(buckets)
    if not buckets:
        return []
    if group_mode == GROUP_MODE_SET:
        labels = [str(bucket.get("label") or "") for bucket in buckets]
        return [
            _bucket(
                _set_bucket_key(key_prefix, labels),
                _set_bucket_label(labels),
            )
        ]
    return buckets


def _field_items(rule, field_slug: str, *, group_items: bool = False):
    cache_key = "_cached_group_items" if group_items else "_cached_object_items"
    for item in getattr(rule, cache_key, []):
        if getattr(item, "exclude", False):
            continue
        field = getattr(item, "field", None)
        if field is None:
            continue
        if (getattr(field, "slug", None) or "") != field_slug:
            continue
        yield item


def _assign_by_column(
    rules: list,
    column_key: str,
    *,
    group_mode: str,
) -> dict[int, list[PolicyGroupBucket]]:
    from netbox_nsm.display_utils import get_display_template_map

    area_slug, type_key = parse_rules_column_key(column_key)
    tmpl_map = get_display_template_map()
    result: dict[int, list[PolicyGroupBucket]] = {}

    for rule in rules:
        buckets: list[PolicyGroupBucket] = []
        if type_key.startswith("ct_"):
            try:
                ct_id = int(type_key[3:])
            except (TypeError, ValueError):
                ct_id = None
            if ct_id is not None:
                for item in _field_items(rule, area_slug):
                    if item.content_type_id != ct_id:
                        continue
                    obj = item.assigned_object
                    if obj is None:
                        continue
                    name = _object_display_name(obj, item.content_type_id, tmpl_map)
                    color = (getattr(obj, "color", None) or "").strip() or None
                    url = (
                        obj.get_absolute_url()
                        if hasattr(obj, "get_absolute_url")
                        else "#"
                    )
                    buckets.append(
                        _bucket(
                            f"col:{column_key}::{name.lower()}",
                            name,
                            url=url,
                            color=color,
                        )
                    )
        result[rule.pk] = _collapse_buckets(
            buckets,
            key_prefix=f"col:{column_key}",
            group_mode=group_mode,
        )
    return result


def _assign_by_field_tag(
    rules: list,
    field_slug: str,
    *,
    group_mode: str,
) -> dict[int, list[PolicyGroupBucket]]:
    result: dict[int, list[PolicyGroupBucket]] = {}

    for rule in rules:
        buckets: list[PolicyGroupBucket] = []
        for item in _field_items(rule, field_slug):
            obj = item.assigned_object
            if obj is None:
                continue
            tags = getattr(obj, "tags", None)
            if tags is None or not hasattr(tags, "all"):
                continue
            for tag in tags.all():
                slug = str(getattr(tag, "slug", None) or tag)
                name = str(tag)
                buckets.append(_bucket(f"tag:{field_slug}::{slug.lower()}", name))
        result[rule.pk] = _collapse_buckets(
            buckets,
            key_prefix=f"tag:{field_slug}",
            group_mode=group_mode,
        )
    return result


def _assign_by_rulebook(rules: list) -> dict[int, list[PolicyGroupBucket]]:
    result: dict[int, list[PolicyGroupBucket]] = {}
    for rule in rules:
        rb = getattr(rule, "rulebook", None)
        if rb is None:
            result[rule.pk] = []
            continue
        name = str(getattr(rb, "name", None) or rb)
        url = rb.get_absolute_url() if hasattr(rb, "get_absolute_url") else "#"
        result[rule.pk] = [
            _bucket(
                f"{GROUP_BY_RULEBOOK}::{rb.pk}",
                name,
                url=url,
            )
        ]
    return result


def _remap_column_bucket_keys(
    buckets: list[PolicyGroupBucket],
    *,
    local_column_key: str,
    global_column_key: str,
) -> list[PolicyGroupBucket]:
    if local_column_key == global_column_key:
        return buckets
    local_prefix = f"col:{local_column_key}"
    global_prefix = f"col:{global_column_key}"
    remapped: list[PolicyGroupBucket] = []
    for bucket in buckets:
        key = str(bucket.get("key") or "")
        if key.startswith(local_prefix):
            key = global_prefix + key[len(local_prefix) :]
        remapped.append(
            PolicyGroupBucket(
                key=key,
                label=bucket.get("label") or "",
                url=bucket.get("url") or "#",
                color=bucket.get("color"),
            )
        )
    return remapped


def assign_rules_to_groups_for_union(
    rules: list,
    mode: str,
    rb_maps: dict[int, dict[str, str]],
    *,
    group_mode: str = GROUP_MODE_SET,
) -> dict[int, list[PolicyGroupBucket]]:
    """Assign groups for all-rules union columns (Area::TypeLabel keys)."""
    if not rules or not mode:
        return {rule.pk: [] for rule in rules}
    if not mode.startswith("col:"):
        return assign_rules_to_groups(rules, mode, group_mode=group_mode)
    global_column_key = mode[4:]
    if not _is_union_column_key(global_column_key):
        return assign_rules_to_groups(rules, mode, group_mode=group_mode)

    result: dict[int, list[PolicyGroupBucket]] = {}
    batches: dict[tuple[int, str], list] = defaultdict(list)
    for rule in rules:
        rb_map = rb_maps.get(rule.rulebook_id, {})
        local_key = rb_map.get(global_column_key)
        if not local_key:
            result[rule.pk] = []
            continue
        batches[(rule.rulebook_id, local_key)].append(rule)

    for (_rb_id, local_key), batch_rules in batches.items():
        assigned = assign_rules_to_groups(
            batch_rules,
            f"col:{local_key}",
            group_mode=group_mode,
        )
        for rule in batch_rules:
            buckets = assigned.get(rule.pk, [])
            result[rule.pk] = _remap_column_bucket_keys(
                buckets,
                local_column_key=local_key,
                global_column_key=global_column_key,
            )
    return result


def assign_rules_to_groups(
    rules: list,
    mode: str,
    *,
    group_mode: str = GROUP_MODE_SET,
    rulebook: Rulebook | None = None,
) -> dict[int, list[PolicyGroupBucket]]:
    del rulebook  # column keys carry full targeting
    if not rules or not mode:
        return {rule.pk: [] for rule in rules}
    if mode == GROUP_BY_RULEBOOK:
        return _assign_by_rulebook(rules)
    if mode.startswith("col:"):
        return _assign_by_column(rules, mode[4:], group_mode=group_mode)
    if mode.startswith("tag:"):
        return _assign_by_field_tag(rules, mode[4:], group_mode=group_mode)
    return {rule.pk: [] for rule in rules}


def _sorted_group_keys(buckets_by_key: dict[str, list]) -> list[str]:
    group_keys = sorted(
        (key for key in buckets_by_key if key != UNGROUPED_GROUP_KEY),
        key=lambda key: ((buckets_by_key[key][0][0] or {}).get("label") or key).lower(),
    )
    if UNGROUPED_GROUP_KEY in buckets_by_key:
        group_keys.append(UNGROUPED_GROUP_KEY)
    return group_keys


def _append_group_header(
    items: list[dict],
    *,
    group_key: str,
    bucket,
    rule_count: int,
    group_level: int = 1,
    parent_key: str | None = None,
) -> None:
    items.append(
        {
            "kind": "group",
            "bucket": bucket,
            "group_key": group_key,
            "group_level": group_level,
            "parent_key": parent_key,
            "rule_count": rule_count,
        }
    )


def _append_group_section(
    items: list[dict],
    *,
    group_key: str,
    bucket,
    rules: list,
    group_level: int = 1,
    parent_key: str | None = None,
) -> None:
    rule_list = list(rules)
    _append_group_header(
        items,
        group_key=group_key,
        bucket=bucket,
        rule_count=len(rule_list),
        group_level=group_level,
        parent_key=parent_key,
    )
    for rule in rule_list:
        items.append(
            {
                "kind": "rule",
                "rule": rule,
                "group_key": group_key,
                "group_level": group_level,
            }
        )


def _lazy_include_rules_for_group(
    group_key: str,
    group_level: int,
    *,
    expanded_keys: set[str] | None,
    collapsed_keys: set[str] | None,
) -> bool:
    return _is_nested_rule_visible(
        {
            "kind": "rule",
            "group_key": group_key,
            "group_level": group_level,
        },
        expanded_keys=expanded_keys,
        collapsed_keys=collapsed_keys,
    )


def _lazy_materialize_group_children(
    group_key: str,
    group_level: int,
    *,
    expanded_keys: set[str] | None,
    collapsed_keys: set[str] | None,
) -> bool:
    if expanded_keys is not None:
        if EXPAND_ALL in expanded_keys:
            return True
        if group_key in expanded_keys:
            return True
        prefix = f"{group_key}::"
        return any(key.startswith(prefix) for key in expanded_keys)
    if collapsed_keys is not None:
        if COLLAPSE_ALL in collapsed_keys:
            return False
        return group_key not in collapsed_keys
    return True


def build_rule_display_items(
    rules: list,
    *,
    rule_to_buckets: dict[int, list[PolicyGroupBucket]],
    enabled: bool = True,
    rule_to_buckets_secondary: dict[int, list[PolicyGroupBucket]] | None = None,
    expanded_keys: set[str] | None = None,
    collapsed_keys: set[str] | None = None,
) -> list[dict]:
    if not rules:
        return []

    if not enabled:
        return [
            {
                "kind": "rule",
                "rule": rule,
                "group_key": UNGROUPED_GROUP_KEY,
                "group_level": 1,
            }
            for rule in rules
        ]

    lazy = expanded_keys is not None or collapsed_keys is not None

    if rule_to_buckets_secondary:
        return _build_nested_rule_display_items(
            rules,
            primary_map=rule_to_buckets,
            secondary_map=rule_to_buckets_secondary,
            expanded_keys=expanded_keys if lazy else None,
            collapsed_keys=collapsed_keys if lazy else None,
        )

    buckets_by_key: dict[str, list] = defaultdict(list)
    for rule in rules:
        buckets = rule_to_buckets.get(rule.pk) or []
        if not buckets:
            buckets_by_key[UNGROUPED_GROUP_KEY].append((None, rule))
            continue
        for bucket in buckets:
            buckets_by_key[bucket["key"]].append((bucket, rule))

    items: list[dict] = []
    for gkey in _sorted_group_keys(buckets_by_key):
        pairs = buckets_by_key[gkey]
        bucket = pairs[0][0] if gkey != UNGROUPED_GROUP_KEY else None
        rule_list = [rule for _bucket, rule in pairs]
        if lazy:
            _append_group_header(
                items,
                group_key=gkey,
                bucket=bucket,
                rule_count=len(rule_list),
                group_level=1,
            )
            if _lazy_include_rules_for_group(
                gkey,
                1,
                expanded_keys=expanded_keys,
                collapsed_keys=collapsed_keys,
            ):
                for rule in rule_list:
                    items.append(
                        {
                            "kind": "rule",
                            "rule": rule,
                            "group_key": gkey,
                            "group_level": 1,
                        }
                    )
            continue
        _append_group_section(
            items,
            group_key=gkey,
            bucket=bucket,
            rules=rule_list,
            group_level=1,
        )
    return items


def _build_nested_rule_display_items(
    rules: list,
    *,
    primary_map: dict[int, list[PolicyGroupBucket]],
    secondary_map: dict[int, list[PolicyGroupBucket]],
    expanded_keys: set[str] | None = None,
    collapsed_keys: set[str] | None = None,
) -> list[dict]:
    lazy = expanded_keys is not None or collapsed_keys is not None
    primary_buckets: dict[str, list] = defaultdict(list)
    for rule in rules:
        buckets = primary_map.get(rule.pk) or []
        if not buckets:
            primary_buckets[UNGROUPED_GROUP_KEY].append((None, rule))
            continue
        for bucket in buckets:
            primary_buckets[bucket["key"]].append((bucket, rule))

    items: list[dict] = []
    for primary_key in _sorted_group_keys(primary_buckets):
        pairs = primary_buckets[primary_key]
        primary_bucket = pairs[0][0] if primary_key != UNGROUPED_GROUP_KEY else None
        primary_rules = [rule for _bucket, rule in pairs]
        _append_group_header(
            items,
            group_key=primary_key,
            bucket=primary_bucket,
            rule_count=len(primary_rules),
            group_level=1,
        )

        materialize_nested = not lazy or _lazy_materialize_group_children(
            primary_key,
            1,
            expanded_keys=expanded_keys,
            collapsed_keys=collapsed_keys,
        )
        if not materialize_nested:
            continue

        secondary_buckets: dict[str, list] = defaultdict(list)
        for rule in primary_rules:
            buckets = secondary_map.get(rule.pk) or []
            if not buckets:
                secondary_buckets[UNGROUPED_GROUP_KEY].append((None, rule))
                continue
            for bucket in buckets:
                nested_key = f"{primary_key}::{bucket['key']}"
                secondary_buckets[nested_key].append((bucket, rule))

        for nested_key in _sorted_group_keys(secondary_buckets):
            nested_pairs = secondary_buckets[nested_key]
            nested_bucket = (
                nested_pairs[0][0]
                if nested_key != f"{primary_key}::{UNGROUPED_GROUP_KEY}"
                and not nested_key.endswith(f"::{UNGROUPED_GROUP_KEY}")
                else None
            )
            nested_rules = [rule for _bucket, rule in nested_pairs]
            if lazy:
                nested_header = {
                    "kind": "group",
                    "group_key": nested_key,
                    "group_level": 2,
                    "parent_key": primary_key,
                }
                if not _is_nested_group_header_visible(
                    nested_header,
                    expanded_keys=expanded_keys,
                    collapsed_keys=collapsed_keys,
                ):
                    continue
                _append_group_header(
                    items,
                    group_key=nested_key,
                    bucket=nested_bucket,
                    rule_count=len(nested_rules),
                    group_level=2,
                    parent_key=primary_key,
                )
                if _lazy_include_rules_for_group(
                    nested_key,
                    2,
                    expanded_keys=expanded_keys,
                    collapsed_keys=collapsed_keys,
                ):
                    for rule in nested_rules:
                        items.append(
                            {
                                "kind": "rule",
                                "rule": rule,
                                "group_key": nested_key,
                                "group_level": 2,
                            }
                        )
                continue
            _append_group_section(
                items,
                group_key=nested_key,
                bucket=nested_bucket,
                rules=nested_rules,
                group_level=2,
                parent_key=primary_key,
            )
    return items


def _preview_group_display_items(group_levels: list[str]) -> list[dict] | None:
    if len(group_levels) <= 1:
        return None
    return [
        {"kind": "group", "group_key": "preview", "group_level": 1},
        {"kind": "group", "group_key": "preview::nested", "group_level": 2},
    ]


def resolve_request_group_expansion(
    request,
    *,
    group_levels: list[str],
    rules_for_preview: list | None = None,
    group_mode: str = GROUP_MODE_SET,
    group_mode_secondary: str | None = None,
) -> tuple[set[str] | None, set[str] | None, int | None]:
    """Resolve group expansion from the request without loading all rules when possible."""
    if not group_levels:
        return None, None, None
    group_by = group_levels[0]
    if "expanded" in request.GET or request.GET.get("collapsed"):
        return resolve_group_expansion(
            request,
            group_by=group_by,
            display_items=_preview_group_display_items(group_levels),
        )
    if parse_group_default_expanded(request) != 1:
        return resolve_group_expansion(
            request,
            group_by=group_by,
            display_items=None,
        )
    preview_rules = rules_for_preview if rules_for_preview is not None else []
    return resolve_group_expansion_for_rules(
        request,
        preview_rules,
        group_levels,
        group_mode=group_mode,
        group_mode_secondary=group_mode_secondary,
    )


def resolve_group_expansion_for_rules(
    request,
    rules: list,
    group_levels: list[str],
    *,
    group_mode: str = GROUP_MODE_SET,
    group_mode_secondary: str | None = None,
) -> tuple[set[str] | None, set[str] | None, int | None]:
    if not group_levels:
        return None, None, None
    primary = group_levels[0]
    secondary_mode = (
        group_mode_secondary if group_mode_secondary is not None else group_mode
    )
    rule_to_primary = assign_rules_to_groups(
        rules,
        primary,
        group_mode=group_mode,
    )
    rule_to_secondary = None
    if len(group_levels) > 1:
        rule_to_secondary = assign_rules_to_groups(
            rules,
            group_levels[1],
            group_mode=secondary_mode,
        )
    display_items = build_rule_display_items(
        rules,
        rule_to_buckets=rule_to_primary,
        enabled=True,
        rule_to_buckets_secondary=rule_to_secondary,
        collapsed_keys={COLLAPSE_ALL},
    )
    return resolve_group_expansion(
        request,
        group_by=primary,
        display_items=display_items,
    )


def filter_collapsed_display_items(
    display_items: list[dict],
    collapsed_keys: set[str] | None,
) -> list[dict]:
    return filter_group_display_items(display_items, collapsed_keys=collapsed_keys)
