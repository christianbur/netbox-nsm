"""Parse, format, and resolve ``nsm_config`` stored in ``CustomObjectType.comments``."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from django.contrib.contenttypes.models import ContentType

from netbox_nsm.core.display_template import DEFAULT_DISPLAY_TEMPLATE, normalize_display_template

__all__ = (
    "NsmTypeConfig",
    "backfill_cot_nsm_config_comments",
    "build_nsm_config_lookup",
    "build_nsm_config_preview_rows",
    "config_dict_from_spec",
    "cot_slug_for_content_type",
    "extract_nsm_config_from_type_comments",
    "filter_assignable_configs",
    "format_nsm_config_comment_yaml",
    "format_type_comments_for_setup_yaml",
    "has_nsm_config_for_content_type",
    "has_nsm_config_in_comments",
    "is_assignable_from_content_type",
    "is_linkable_content_type",
    "iter_linkable_configs",
    "normalize_nsm_config_list",
    "parse_nsm_config_from_comments",
    "resolve_nsm_config_dict_for_cot",
    "resolve_nsm_config_for_cot",
    "resolve_nsm_config_for_content_type",
    "sync_cot_nsm_config_comments",
    "sync_cot_nsm_config_comments_for_slugs",
    "parse_nsm_config_document_from_comments",
    "merge_nsm_config_document_into_comments",
    "save_nsm_config_document_for_cot",
    "clear_nsm_config_from_cot_comments",
)

_COT_MODEL_RE = re.compile(r"table(\d+)model", re.IGNORECASE)
_MARKDOWN_FENCE_RE = re.compile(
    r"^\s*```(?:\w*)?\s*\r?\n(.*)\r?\n```\s*$",
    re.DOTALL,
)

_RULE_VIEW_KEYS = frozenset({"sort_order", "display_template", "areas"})


def _normalized_display_template(value: str | None) -> str:
    return normalize_display_template(value or DEFAULT_DISPLAY_TEMPLATE)


def _areas_for_cot_slug(slug: str) -> list[str]:
    from netbox_nsm.objects.builtin_types import BUILTIN_CUSTOM_TYPES
    from netbox_nsm.bundles.schema_builder import iter_types

    for _typedef, _base_slug, cot_slug, areas in iter_types(BUILTIN_CUSTOM_TYPES):
        if cot_slug == slug:
            return list(areas)
    return []



def cot_slug_for_content_type(content_type: ContentType) -> str | None:
    """Return COT slug when *content_type* belongs to a CustomObjectType model."""
    if content_type.app_label != "netbox_custom_objects":
        return None
    match = _COT_MODEL_RE.match(content_type.model)
    if not match:
        return None
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return None
    cot = CustomObjectType.objects.filter(pk=int(match.group(1))).only("slug").first()
    return cot.slug if cot else None


def config_dict_from_spec(spec: dict) -> dict[str, Any]:
    """Build a normalized config dict from a ``TYPECONFIG_*`` spec."""
    from netbox_nsm.type_metadata.roles import default_role_for_slug
    slug = spec.get("slug", "")
    result = {
        "sort_order": spec.get("sort_order", 0),
        "display_template": _normalized_display_template(spec.get("display_template")),
        "areas": list(spec.get("areas") or _areas_for_cot_slug(slug)),
    }
    role = default_role_for_slug(slug)
    if role:
        result["role"] = role
    return result


def normalize_nsm_config_list(raw_list: list | None) -> dict[str, Any] | None:
    """Merge segmented ``nsm_config`` list entries into a flat dict."""
    if not raw_list:
        return None

    merged: dict[str, Any] = {}
    for entry in raw_list:
        if not isinstance(entry, dict):
            continue
        if len(entry) == 1 and "rule_view" in entry:
            block = entry.get("rule_view") or {}
            if isinstance(block, dict):
                for key in _RULE_VIEW_KEYS:
                    if key in block:
                        merged[key] = block[key]
            continue
        # Legacy flat keys and ``- sort_order:`` list items.
        for key in _RULE_VIEW_KEYS:
            if key in entry:
                merged[key] = entry[key]
        if len(entry) == 1:
            key, value = next(iter(entry.items()))
            if key in _RULE_VIEW_KEYS:
                merged[key] = value
            elif key == "link_table":
                merged["link_table"] = bool(value)

    if not merged:
        return None
    merged.setdefault("display_template", DEFAULT_DISPLAY_TEMPLATE)
    merged["display_template"] = _normalized_display_template(merged.get("display_template"))
    merged.setdefault("sort_order", 0)
    return merged


def _strip_markdown_fence(text: str) -> str:
    """Return inner YAML when *text* is wrapped in markdown code fences."""
    if not text:
        return text
    match = _MARKDOWN_FENCE_RE.match(text)
    if match:
        return match.group(1)
    return text


def _wrap_yaml_in_markdown_fence(yaml_text: str) -> str:
    """Wrap YAML in plain markdown ``` fences for ``CustomObjectType.comments``."""
    content = (yaml_text or "").rstrip()
    if not content:
        return ""
    return f"```\n{content}\n```\n"


def _load_yaml_document(text: str) -> Any:
    import yaml

    return yaml.safe_load(_strip_markdown_fence(text or ""))


def _extract_nsm_config_list_from_document(document: Any) -> list | None:
    if not isinstance(document, dict):
        return None
    raw = document.get("nsm_config")
    if isinstance(raw, list):
        return raw
    return None


def parse_nsm_config_from_comments(text: str) -> dict[str, Any] | None:
    """Parse canonical ``nsm_config`` YAML from ``CustomObjectType.comments``."""
    document = _load_yaml_document(text)
    raw_list = _extract_nsm_config_list_from_document(document)
    return normalize_nsm_config_list(raw_list)


def extract_nsm_config_from_type_comments(type_def: dict) -> dict[str, Any] | None:
    """Parse ``comments`` from a setup portable-schema type definition."""
    comments = type_def.get("comments")
    if comments is None:
        return None
    if isinstance(comments, str):
        return parse_nsm_config_from_comments(comments)
    if not isinstance(comments, list):
        return None
    for entry in comments:
        if not isinstance(entry, dict) or "nsm_config" not in entry:
            continue
        return normalize_nsm_config_list(entry.get("nsm_config"))
    return None


def has_nsm_config_in_comments(text: str) -> bool:
    return parse_nsm_config_from_comments(text) is not None


def _normalize_config_dict(config: dict[str, Any]) -> dict[str, Any]:
    result = {
        "sort_order": int(config.get("sort_order", 0)),
        "display_template": _normalized_display_template(config.get("display_template")),
    }
    if "areas" in config:
        result["areas"] = list(config.get("areas") or [])
    if "role" in config:
        result["role"] = config.get("role")
    if "menu" in config:
        result["menu"] = config.get("menu")
    return result


def _build_nsm_config_list(config: dict[str, Any]) -> list[dict]:
    normalized = _normalize_config_dict(config)
    rule_view_block = {
        "sort_order": normalized["sort_order"],
        "display_template": normalized["display_template"],
    }
    if normalized.get("areas"):
        rule_view_block["areas"] = list(normalized["areas"])
    segments: list[dict] = [{"rule_view": rule_view_block}]
    role = normalized.get("role")
    if isinstance(role, str) and role.strip():
        segments.append({"role": role.strip()})
    menu = normalized.get("menu")
    if isinstance(menu, str) and menu.strip():
        segments.append({"menu": menu.strip()})
    return segments


def format_nsm_config_comment_yaml(config: dict[str, Any]) -> str:
    """Return canonical ``nsm_config`` YAML for ``CustomObjectType.comments``."""
    import yaml

    payload = {"nsm_config": _build_nsm_config_list(config)}
    yaml_body = (
        yaml.dump(
            payload,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).rstrip()
        + "\n"
    )
    return _wrap_yaml_in_markdown_fence(yaml_body)


def format_type_comments_for_setup_yaml(config: dict[str, Any]) -> list[dict]:
    """Build ``comments`` list for setup portable-schema export."""
    return [{"nsm_config": _build_nsm_config_list(config)}]


def _document_to_nsm_config_segments(document: dict[str, Any]) -> list[dict]:
    from netbox_nsm.type_metadata.rulebook import (
        _rulebook_block_for_yaml,
        is_default_rulebook_config,
        normalize_rulebook_config,
    )

    segments: list[dict] = []
    rule_view = document.get("rule_view")
    if isinstance(rule_view, dict) and rule_view:
        block = {
            "sort_order": int(rule_view.get("sort_order", 0)),
            "display_template": _normalized_display_template(rule_view.get("display_template")),
        }
        if rule_view.get("areas"):
            block["areas"] = list(rule_view.get("areas") or [])
        segments.append({"rule_view": block})
    role = document.get("role")
    if isinstance(role, str) and role.strip():
        segments.append({"role": role.strip()})
    menu = document.get("menu")
    if isinstance(menu, str) and menu.strip():
        segments.append({"menu": menu.strip()})
    if document.get("link_table"):
        segments.append({"link_table": True})
    if "rulebook" in document:
        normalized = normalize_rulebook_config(document.get("rulebook"))
        if not is_default_rulebook_config(normalized):
            segments.append({"rulebook": _rulebook_block_for_yaml(normalized)})
    types_map = document.get("types")
    if isinstance(types_map, dict) and types_map:
        from netbox_nsm.type_metadata.rule_view import compact_rulebook_types_map

        compacted = compact_rulebook_types_map(types_map)
        if compacted:
            segments.append({"types": deepcopy(compacted)})
    return segments


def _format_comments_with_nsm_document(
    existing_comments: str,
    nsm_document: dict[str, Any],
) -> str:
    import yaml

    document = _load_yaml_document(existing_comments)
    if not isinstance(document, dict):
        document = {}
    segments = _document_to_nsm_config_segments(nsm_document)
    if segments:
        document["nsm_config"] = segments
    else:
        document.pop("nsm_config", None)
    if not document:
        return ""
    yaml_body = (
        yaml.dump(
            document,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).rstrip()
        + "\n"
    )
    return _wrap_yaml_in_markdown_fence(yaml_body)


def _stored_nsm_config_document(text: str) -> dict[str, Any]:
    """Return only ``nsm_config`` segments present in *text* (no rulebook defaults)."""
    result: dict[str, Any] = {}
    policy = parse_nsm_config_from_comments(text)
    if policy:
        result["rule_view"] = {
            "sort_order": int(policy.get("sort_order", 0)),
            "display_template": _normalized_display_template(policy.get("display_template")),
        }
        if policy.get("areas"):
            result["rule_view"]["areas"] = list(policy.get("areas") or [])
    from netbox_nsm.type_metadata.roles import parse_role_from_comments
    from netbox_nsm.type_metadata.menus import parse_menu_from_comments

    role = parse_role_from_comments(text)
    if role:
        result["role"] = role
    menu = parse_menu_from_comments(text)
    if menu:
        result["menu"] = menu
    parsed = parse_nsm_config_from_comments(text)
    if parsed and parsed.get("link_table"):
        result["link_table"] = bool(parsed["link_table"])
    if result:
        return result
    return {}


def parse_nsm_config_document_from_comments(text: str) -> dict[str, Any]:
    """Return API-friendly ``nsm_config`` segments from ``comments`` YAML."""
    from netbox_nsm.type_metadata.rulebook import (
        normalize_rulebook_config,
        parse_rulebook_config_from_comments,
    )

    result = _stored_nsm_config_document(text)
    if "rulebook" not in result:
        result["rulebook"] = normalize_rulebook_config(
            parse_rulebook_config_from_comments(text)
        )
    return result


def merge_nsm_config_document_into_comments(
    existing_comments: str,
    updates: dict[str, Any],
) -> str:
    """Merge ``rule_view`` / ``rulebook`` segments into comments."""
    current = _stored_nsm_config_document(existing_comments)
    for key in ("rule_view", "rulebook", "types", "role", "menu", "link_table"):
        if key not in updates:
            continue
        value = updates[key]
        if value is None:
            current.pop(key, None)
        else:
            current[key] = value
    return _format_comments_with_nsm_document(existing_comments, current)


def save_nsm_config_document_for_cot(cot, updates: dict[str, Any], *, rulebook_cot=None) -> None:
    """Persist ``nsm_config`` segments on COT ``comments`` (partial merge)."""
    from django.core.exceptions import ValidationError

    if "rulebook" in updates and updates["rulebook"] is not None:
        from netbox_nsm.rulebooks.cot_hierarchy import validate_cot_parent_slug

        parent = (updates["rulebook"].get("parent_slug") or "").strip()
        if parent:
            error = validate_cot_parent_slug(cot.slug, parent)
            if error:
                raise ValidationError(error)

    target_cot = cot
    merge_updates = dict(updates)

    if "rule_view" in merge_updates and rulebook_cot is not None:
        from netbox_nsm.type_metadata.rule_view import compact_rulebook_types_map

        policy_slug = cot.slug
        rule_view = merge_updates.pop("rule_view")
        rb_doc = _stored_nsm_config_document(rulebook_cot.comments or "")
        types_map = dict(rb_doc.get("types") or {})
        if rule_view is None:
            types_map.pop(policy_slug, None)
        else:
            entry = dict(types_map.get(policy_slug) or {})
            entry["rule_view"] = rule_view
            types_map[policy_slug] = entry
        rb_updates = {"types": compact_rulebook_types_map(types_map)}
        if "rulebook" in merge_updates:
            rb_updates["rulebook"] = merge_updates.pop("rulebook")
        new_comments = merge_nsm_config_document_into_comments(
            rulebook_cot.comments or "",
            rb_updates,
        ).rstrip()
        if rulebook_cot.comments != new_comments:
            rulebook_cot.comments = new_comments
            rulebook_cot.save(update_fields=["comments"])
        if not merge_updates:
            if "rule_view" in updates:
                from netbox_nsm.core.display_utils import get_display_template_map

                get_display_template_map.cache_clear()
            return

    if "types" in merge_updates and cot.slug.startswith("nsm_rb_"):
        from netbox_nsm.type_metadata.rule_view import compact_rulebook_types_map

        merge_updates["types"] = compact_rulebook_types_map(merge_updates["types"])
    elif "types" in merge_updates:
        merge_updates.pop("types", None)

    new_comments = merge_nsm_config_document_into_comments(
        target_cot.comments or "",
        merge_updates,
    ).rstrip()
    if target_cot.comments == new_comments:
        if "rule_view" in updates or "types" in updates:
            from netbox_nsm.core.display_utils import get_display_template_map

            get_display_template_map.cache_clear()
        return
    target_cot.comments = new_comments
    target_cot.save(update_fields=["comments"])
    if "rule_view" in updates or "types" in updates:
        from netbox_nsm.core.display_utils import get_display_template_map

        get_display_template_map.cache_clear()


def clear_nsm_config_from_cot_comments(cot) -> None:
    """Remove the ``nsm_config`` block from *cot* ``comments``."""
    new_comments = merge_nsm_config_document_into_comments(
        cot.comments or "",
        {
            "rule_view": None,
            "rulebook": None,
            "types": None,
            "role": None,
        },
    ).rstrip()
    if cot.comments == new_comments:
        return
    cot.comments = new_comments
    cot.save(update_fields=["comments"])


@dataclass
class NsmTypeConfig:
    """Resolved NSM settings for one Custom Object Type."""

    slug: str
    content_type_id: int
    name: str
    sort_order: int = 0
    display_template: str = DEFAULT_DISPLAY_TEMPLATE
    role: str | None = None

    @property
    def role_label(self) -> str:
        if not self.role:
            return ""
        from netbox_nsm.type_metadata.roles import COT_ROLE_CHOICES

        for value, label in COT_ROLE_CHOICES:
            if value == self.role:
                return str(label)
        return self.role

    @property
    def content_type_label(self) -> str:
        if not self.content_type_id:
            return ""
        ct = ContentType.objects.filter(pk=self.content_type_id).first()
        if not ct:
            return ""
        mc = ct.model_class()
        if mc:
            vn = mc._meta.verbose_name
            if vn:
                return str(vn).title()
        return ct.model.replace("_", " ").title()


def _build_nsm_type_config(
    *,
    slug: str,
    content_type_id: int,
    name: str,
    config: dict[str, Any],
) -> NsmTypeConfig:
    normalized = _normalize_config_dict(config)
    return NsmTypeConfig(
        slug=slug,
        content_type_id=content_type_id,
        name=name,
        sort_order=normalized["sort_order"],
        display_template=normalized["display_template"],
        role=normalized.get("role"),
    )


def _rule_view_from_rulebook_comments(rulebook_cot, policy_slug: str) -> dict[str, Any] | None:
    if rulebook_cot is None:
        return None
    rb_doc = _stored_nsm_config_document(rulebook_cot.comments or "")
    type_block = (rb_doc.get("types") or {}).get(policy_slug) or {}
    rule_view = type_block.get("rule_view")
    return rule_view if isinstance(rule_view, dict) else None


def _merge_parsed_into_config(
    base: dict[str, Any],
    parsed: dict[str, Any],
) -> dict[str, Any]:
    result = deepcopy(base)
    for key in ("sort_order", "display_template", "areas"):
        if key in parsed:
            result[key] = parsed[key]
    if "role" in parsed:
        result["role"] = parsed["role"]
    if "link_table" in parsed:
        result["link_table"] = bool(parsed["link_table"])
    return result


def resolve_nsm_config_dict_for_cot(
    cot,
    *,
    rulebook_cot=None,
) -> dict[str, Any] | None:
    """Return merged spec + comments config dict for *cot*."""
    from netbox_nsm.type_metadata.roles import parse_role_from_comments, resolve_role_for_cot
    from netbox_nsm.type_metadata.specs import TYPECONFIG_SPEC_BY_SLUG

    comments = getattr(cot, "comments", "") or ""
    spec = TYPECONFIG_SPEC_BY_SLUG.get(cot.slug)
    if spec:
        config = config_dict_from_spec(spec)
        rule_view = _rule_view_from_rulebook_comments(rulebook_cot, cot.slug)
        if rule_view:
            config.update(rule_view)
        elif not rulebook_cot:
            parsed = parse_nsm_config_from_comments(comments)
            if parsed:
                config = _merge_parsed_into_config(config, parsed)
    else:
        config = {
            "sort_order": 0,
            "display_template": DEFAULT_DISPLAY_TEMPLATE,
            "areas": [],
        }
        parsed = parse_nsm_config_from_comments(comments)
        if parsed:
            config = _merge_parsed_into_config(config, parsed)

    role = parse_role_from_comments(comments) or resolve_role_for_cot(cot)
    if role:
        config["role"] = role
    return config


def resolve_nsm_config_for_cot(cot, *, rulebook_cot=None) -> NsmTypeConfig | None:
    """Resolve settings for *cot* from comments with spec fallback."""
    from django.contrib.contenttypes.models import ContentType as DjCT

    from netbox_nsm.type_metadata.roles import resolve_role_for_cot
    from netbox_nsm.type_metadata.specs import TYPECONFIG_SPEC_BY_SLUG

    config_dict = resolve_nsm_config_dict_for_cot(cot, rulebook_cot=rulebook_cot)
    if config_dict is None:
        return None
    if resolve_role_for_cot(cot) != "rulebook" and cot.slug not in TYPECONFIG_SPEC_BY_SLUG:
        return None
    spec = TYPECONFIG_SPEC_BY_SLUG.get(cot.slug)
    ct = DjCT.objects.get_for_model(cot.get_model())
    name = spec["label"] if spec else (getattr(cot, "name", None) or cot.slug)

    return _build_nsm_type_config(
        slug=cot.slug,
        content_type_id=ct.pk,
        name=name,
        config=config_dict,
    )


def resolve_nsm_config_for_content_type(
    content_type_id: int,
    *,
    rulebook_cot=None,
) -> NsmTypeConfig | None:
    ct = ContentType.objects.filter(pk=content_type_id).first()
    if not ct:
        return None
    slug = cot_slug_for_content_type(ct)
    if not slug:
        return None
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return None
    cot = CustomObjectType.objects.filter(slug=slug).first()
    if not cot:
        return None
    return resolve_nsm_config_for_cot(cot, rulebook_cot=rulebook_cot)


def build_nsm_config_lookup(*, rulebook_cot=None) -> dict[int, NsmTypeConfig]:
    """Map ``content_type_id`` → resolved config for all UI COT slugs."""
    from netbox_custom_objects.models import CustomObjectType

    from netbox_nsm.type_metadata.specs import TYPECONFIG_UI_SPECS

    lookup: dict[int, NsmTypeConfig] = {}
    slugs = [spec["slug"] for spec in TYPECONFIG_UI_SPECS]
    for cot in CustomObjectType.objects.filter(slug__in=slugs):
        resolved = resolve_nsm_config_for_cot(cot, rulebook_cot=rulebook_cot)
        if resolved:
            lookup[resolved.content_type_id] = resolved
    return lookup


def iter_linkable_configs():
    """Yield all UI configs for the Security Links assign picker."""
    yield from build_nsm_config_lookup().values()


def filter_assignable_configs(assigner_content_type_id: int) -> list[NsmTypeConfig]:
    """All UI configs are assignable from any NetBox object type."""
    del assigner_content_type_id
    return sorted(
        iter_linkable_configs(),
        key=lambda c: (c.name or "").lower(),
    )


def is_linkable_content_type(content_type_id: int) -> bool:
    return has_nsm_config_for_content_type(content_type_id)


def is_assignable_from_content_type(
    assigner_content_type_id: int, target_content_type_id: int
) -> bool:
    del assigner_content_type_id
    return is_linkable_content_type(target_content_type_id)


def has_nsm_config_for_content_type(content_type_id: int) -> bool:
    return resolve_nsm_config_for_content_type(content_type_id) is not None


def build_nsm_config_preview_rows(config: NsmTypeConfig) -> list[dict]:
    from django.utils.translation import gettext_lazy as _

    return [
        {"label": str(_("Name")), "value": config.name, "group": "rule_view"},
        {
            "label": str(_("Sort order")),
            "value": str(config.sort_order),
            "group": "rule_view",
        },
        {
            "label": str(_("Slug")),
            "value": config.slug,
            "mono": True,
            "group": "rule_view",
        },
        {
            "label": str(_("Display Template")),
            "value": config.display_template,
            "mono": True,
            "group": "rule_view",
        },
    ]


def sync_cot_nsm_config_comments(cot, *, spec: dict | None = None) -> bool:
    """Write bundled defaults into COT ``comments``."""
    from netbox_nsm.type_metadata.specs import (
        TYPECONFIG_LIST_EXCLUDED_SLUGS,
        TYPECONFIG_SPEC_BY_SLUG,
    )

    if cot.slug in TYPECONFIG_LIST_EXCLUDED_SLUGS:
        return False
    if spec is None:
        spec = TYPECONFIG_SPEC_BY_SLUG.get(cot.slug)
    if not spec:
        return False
    config = config_dict_from_spec(spec)
    updates: dict[str, Any] = {
        "rule_view": {
            "sort_order": config.get("sort_order", 0),
            "display_template": _normalized_display_template(config.get("display_template")),
        },
    }
    if config.get("areas"):
        updates["rule_view"]["areas"] = list(config["areas"])
    if config.get("role"):
        updates["role"] = config["role"]
    before = (cot.comments or "").rstrip()
    save_nsm_config_document_for_cot(cot, updates)
    cot.refresh_from_db()
    return (cot.comments or "").rstrip() != before


def sync_cot_nsm_config_comments_for_slugs(slugs) -> int:
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return 0

    from netbox_nsm.type_metadata.specs import TYPECONFIG_SPEC_BY_SLUG

    updated = 0
    for cot in CustomObjectType.objects.filter(slug__in=slugs):
        if sync_cot_nsm_config_comments(
            cot, spec=TYPECONFIG_SPEC_BY_SLUG.get(cot.slug)
        ):
            updated += 1
    return updated


def backfill_cot_nsm_config_comments() -> int:
    from netbox_nsm.type_metadata.specs import TYPECONFIG_UI_SPECS

    return sync_cot_nsm_config_comments_for_slugs(
        [spec["slug"] for spec in TYPECONFIG_UI_SPECS]
    )
