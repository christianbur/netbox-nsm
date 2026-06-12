"""Parse, format, and resolve ``nsm_config`` stored in ``CustomObjectType.comments``."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from django.contrib.contenttypes.models import ContentType

__all__ = (
    "NsmTypeConfig",
    "resolve_object_builder_config_for_cot",
    "backfill_cot_nsm_config_comments",
    "build_nsm_config_lookup",
    "build_nsm_config_preview_rows",
    "config_dict_from_spec",
    "config_dict_from_typeconfig",
    "cot_slug_for_content_type",
    "extract_nsm_config_from_type_comments",
    "filter_assignable_configs",
    "format_nsm_config_comment_yaml",
    "format_type_comments_for_setup_yaml",
    "has_nsm_config_for_content_type",
    "has_nsm_config_in_comments",
    "is_assignable_from_content_type",
    "is_panel_linkable_content_type",
    "iter_panel_linkable_configs",
    "normalize_nsm_config_list",
    "parse_nsm_config_from_comments",
    "resolve_nsm_config_for_cot",
    "resolve_nsm_config_for_content_type",
    "sync_cot_nsm_config_comments",
    "sync_cot_nsm_config_comments_for_slugs",
)

_COT_MODEL_RE = re.compile(r"table(\d+)model", re.IGNORECASE)

_RULE_VIEW_KEYS = frozenset({"sort_order", "display_template"})


def _merge_object_builder_block(merged: dict[str, Any], block: dict) -> None:
    from netbox_nsm.objects.object_builder_config import normalize_object_builder_config

    merged["object_builder"] = normalize_object_builder_config(block)


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
    from netbox_nsm.objects.object_builder_config import object_builder_config_from_spec

    result = {
        "sort_order": spec.get("sort_order", 0),
        "display_template": spec.get("display_template") or "{name}",
    }
    object_builder = object_builder_config_from_spec(spec)
    if object_builder is not None:
        result["object_builder"] = object_builder
    return result


def config_dict_from_typeconfig(type_config) -> dict[str, Any]:
    """Build a normalized config dict from a legacy ``TypeConfig`` row."""
    return {
        "sort_order": type_config.sort_order,
        "display_template": type_config.display_template or "{name}",
    }


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
        if len(entry) == 1 and "object_builder" in entry:
            block = entry.get("object_builder") or {}
            if isinstance(block, dict):
                _merge_object_builder_block(merged, block)
            continue
        # Legacy flat keys and ``- sort_order:`` list items.
        for key in _RULE_VIEW_KEYS:
            if key in entry:
                merged[key] = entry[key]
        if len(entry) == 1:
            key, value = next(iter(entry.items()))
            if key in _RULE_VIEW_KEYS:
                merged[key] = value

    if not merged:
        return None
    merged.setdefault("display_template", "{name}")
    merged.setdefault("sort_order", 0)
    return merged


def _load_yaml_document(text: str) -> Any:
    import yaml

    return yaml.safe_load(text or "")


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
    return {
        "sort_order": int(config.get("sort_order", 0)),
        "display_template": config.get("display_template") or "{name}",
    }


def _build_nsm_config_list(config: dict[str, Any]) -> list[dict]:
    from netbox_nsm.objects.object_builder_config import normalize_object_builder_config

    normalized = _normalize_config_dict(config)
    segments: list[dict] = [
        {
            "rule_view": {
                "sort_order": normalized["sort_order"],
                "display_template": normalized["display_template"],
            }
        }
    ]
    if "object_builder" in config:
        segments.append(
            {
                "object_builder": normalize_object_builder_config(
                    config.get("object_builder")
                )
            }
        )
    return segments


def format_nsm_config_comment_yaml(config: dict[str, Any]) -> str:
    """Return canonical ``nsm_config`` YAML for ``CustomObjectType.comments``."""
    import yaml

    payload = {"nsm_config": _build_nsm_config_list(config)}
    return (
        yaml.dump(
            payload,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).rstrip()
        + "\n"
    )


def format_type_comments_for_setup_yaml(config: dict[str, Any]) -> list[dict]:
    """Build ``comments`` list for setup portable-schema export."""
    return [{"nsm_config": _build_nsm_config_list(config)}]


@dataclass
class NsmTypeConfig:
    """Resolved NSM settings for one Custom Object Type."""

    slug: str
    content_type_id: int
    name: str
    sort_order: int = 0
    display_template: str = "{name}"

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
    )


def resolve_nsm_config_for_cot(cot) -> NsmTypeConfig | None:
    """Resolve settings for *cot* from comments with spec fallback."""
    from django.contrib.contenttypes.models import ContentType as DjCT

    from netbox_nsm.objects.type_config_specs import TYPECONFIG_SPEC_BY_SLUG

    spec = TYPECONFIG_SPEC_BY_SLUG.get(cot.slug)
    if not spec:
        return None
    ct = DjCT.objects.get_for_model(cot.get_model())
    parsed = parse_nsm_config_from_comments(cot.comments or "")
    config = parsed or config_dict_from_spec(spec)
    return _build_nsm_type_config(
        slug=cot.slug,
        content_type_id=ct.pk,
        name=spec["label"],
        config=config,
    )


def resolve_nsm_config_for_content_type(content_type_id: int) -> NsmTypeConfig | None:
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
    return resolve_nsm_config_for_cot(cot)


def build_nsm_config_lookup() -> dict[int, NsmTypeConfig]:
    """Map ``content_type_id`` → resolved config for all UI COT slugs."""
    from netbox_custom_objects.models import CustomObjectType

    from netbox_nsm.objects.type_config_specs import TYPECONFIG_UI_SPECS

    lookup: dict[int, NsmTypeConfig] = {}
    slugs = [spec["slug"] for spec in TYPECONFIG_UI_SPECS]
    for cot in CustomObjectType.objects.filter(slug__in=slugs):
        resolved = resolve_nsm_config_for_cot(cot)
        if resolved:
            lookup[resolved.content_type_id] = resolved
    return lookup


def iter_panel_linkable_configs():
    """Yield all UI configs for the Security Panel assign picker."""
    yield from build_nsm_config_lookup().values()


def filter_assignable_configs(assigner_content_type_id: int) -> list[NsmTypeConfig]:
    """All UI configs are assignable from any NetBox object type."""
    del assigner_content_type_id
    return sorted(
        iter_panel_linkable_configs(),
        key=lambda c: (c.name or "").lower(),
    )


def is_panel_linkable_content_type(content_type_id: int) -> bool:
    return has_nsm_config_for_content_type(content_type_id)


def is_assignable_from_content_type(
    assigner_content_type_id: int, target_content_type_id: int
) -> bool:
    del assigner_content_type_id
    return has_nsm_config_for_content_type(target_content_type_id)


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
    """Set ``CustomObjectType.comments`` from bundled ``nsm_config`` YAML."""
    from netbox_nsm.objects.type_config_specs import (
        TYPECONFIG_LIST_EXCLUDED_SLUGS,
        TYPECONFIG_SPEC_BY_SLUG,
    )

    if cot.slug in TYPECONFIG_LIST_EXCLUDED_SLUGS:
        return False
    if spec is None:
        spec = TYPECONFIG_SPEC_BY_SLUG.get(cot.slug)
    if not spec:
        return False
    new_comments = format_nsm_config_comment_yaml(config_dict_from_spec(spec)).rstrip()
    if cot.comments == new_comments:
        return False
    cot.comments = new_comments
    cot.save(update_fields=["comments"])
    return True


def sync_cot_nsm_config_comments_for_slugs(slugs) -> int:
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return 0

    from netbox_nsm.objects.type_config_specs import TYPECONFIG_SPEC_BY_SLUG

    updated = 0
    for cot in CustomObjectType.objects.filter(slug__in=slugs):
        if sync_cot_nsm_config_comments(
            cot, spec=TYPECONFIG_SPEC_BY_SLUG.get(cot.slug)
        ):
            updated += 1
    return updated


def resolve_object_builder_config_for_cot(cot) -> dict[str, Any] | None:
    """Return normalized ``object_builder`` config for *cot*, or ``None``."""
    from netbox_nsm.objects.object_builder_config import (
        normalize_object_builder_config,
        object_builder_config_from_spec,
    )
    from netbox_nsm.objects.type_config_specs import TYPECONFIG_SPEC_BY_SLUG

    if cot.slug != "nsm_address":
        return None
    parsed = parse_nsm_config_from_comments(cot.comments or "")
    if parsed and "object_builder" in parsed:
        return normalize_object_builder_config(parsed["object_builder"])
    spec = TYPECONFIG_SPEC_BY_SLUG.get(cot.slug)
    return object_builder_config_from_spec(spec)


def backfill_cot_nsm_config_comments() -> int:
    from netbox_nsm.objects.type_config_specs import TYPECONFIG_UI_SPECS

    return sync_cot_nsm_config_comments_for_slugs(
        [spec["slug"] for spec in TYPECONFIG_UI_SPECS]
    )
