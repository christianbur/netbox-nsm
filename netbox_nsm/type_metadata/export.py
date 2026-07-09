"""Serialize Object Config (nsm_config) settings to YAML."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _

from netbox_nsm.core.display_template import DEFAULT_DISPLAY_TEMPLATE
from netbox_nsm.type_metadata.config import (
    NsmTypeConfig,
    apply_schema_bundle_metadata,
    build_nsm_config_lookup,
    build_nsm_config_preview_rows,
    config_dict_from_metadata_block,
    cot_slug_for_content_type,
    format_nsm_config_comment_yaml,
    metadata_block_for_cot_slug,
    resolve_nsm_config_for_cot,
)

__all__ = (
    "apply_schema_bundle_metadata",
    "build_all_type_configs_preview_rows",
    "build_type_config_export_data",
    "build_type_config_preview_rows",
    "content_type_export_ref",
    "cot_slug_for_content_type",
    "export_all_type_configs_yaml",
    "export_type_config_yaml",
    "format_all_type_configs_comment_yaml",
    "format_type_config_comment_yaml",
    "format_type_config_comment_yaml_for_metadata_block",
    "format_type_config_comment_yaml_for_config",
)


def content_type_export_ref(content_type: ContentType) -> str:
    """Portable reference: COT slug when available, else ``app_label.model``."""
    slug = cot_slug_for_content_type(content_type)
    if slug:
        return slug
    return f"{content_type.app_label}.{content_type.model}"


def build_type_config_export_data(config: NsmTypeConfig) -> dict:
    """Build a plain dict of Object Config settings for YAML export."""
    return {
        "sort_order": config.sort_order,
        "display_template": config.display_template or DEFAULT_DISPLAY_TEMPLATE,
    }


def format_type_config_comment_yaml(
    sort_order: int,
    display_template: str,
) -> str:
    """Return canonical ``nsm_config`` YAML (legacy two-arg helper)."""
    return format_nsm_config_comment_yaml(
        {
            "sort_order": sort_order,
            "display_template": display_template or DEFAULT_DISPLAY_TEMPLATE,
        }
    )


def format_type_config_comment_yaml_for_metadata_block(block: dict) -> str:
    """YAML section for a bundle ``metadata`` block."""
    return format_nsm_config_comment_yaml(config_dict_from_metadata_block(block))


def format_type_config_comment_yaml_for_config(config: NsmTypeConfig) -> str:
    """YAML section reflecting resolved Object Config."""
    return format_nsm_config_comment_yaml(
        {
            "sort_order": config.sort_order,
            "display_template": config.display_template,
        }
    )


def format_all_type_configs_comment_yaml() -> str:
    """All bundled UI Object Config definitions from ``nsm_schema`` metadata."""
    from netbox_nsm.type_metadata.specs import REQUIRED_COT_SLUGS, TYPECONFIG_LIST_EXCLUDED_SLUGS

    rows: list[tuple[int, str, dict]] = []
    for slug in REQUIRED_COT_SLUGS:
        if slug in TYPECONFIG_LIST_EXCLUDED_SLUGS:
            continue
        block = metadata_block_for_cot_slug(slug)
        if not block:
            continue
        cfg = config_dict_from_metadata_block(block)
        rows.append((int(cfg.get("sort_order", 0)), slug, block))
    sections = [
        format_type_config_comment_yaml_for_metadata_block(block).rstrip()
        for _sort, _slug, block in sorted(rows, key=lambda item: (item[0], item[1]))
    ]
    return "\n\n".join(sections) + ("\n" if sections else "")


def _resolved_ui_configs() -> list[NsmTypeConfig]:
    return sorted(
        build_nsm_config_lookup().values(),
        key=lambda item: (item.sort_order, item.name),
    )


def export_type_config_yaml(config: NsmTypeConfig) -> str:
    return format_type_config_comment_yaml_for_config(config)


def export_all_type_configs_yaml(configs=None) -> str:
    if configs is None:
        configs = _resolved_ui_configs()
    sections = [format_type_config_comment_yaml_for_config(cfg).rstrip() for cfg in configs]
    return "\n\n".join(sections) + "\n"


def build_all_type_configs_preview_rows(configs=None) -> list[dict]:
    if configs is None:
        configs = _resolved_ui_configs()
    return [
        {
            "name": cfg.name,
            "sort_order": cfg.sort_order,
            "slug": cfg.slug,
            "display_template": cfg.display_template or DEFAULT_DISPLAY_TEMPLATE,
        }
        for cfg in configs
    ]


def build_type_config_preview_rows(config: NsmTypeConfig) -> list[dict]:
    """Human-readable setting rows for the Preview tab."""
    rows = build_nsm_config_preview_rows(config)
    if config.content_type_id:
        rows.insert(
            3,
            {
                "label": str(_("Object Type")),
                "value": config.content_type_label,
                "group": "rule_view",
            },
        )
    return rows
