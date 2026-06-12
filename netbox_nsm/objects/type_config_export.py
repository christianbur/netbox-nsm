"""Serialize Object Config (nsm_config) settings to YAML."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _

from netbox_nsm.objects.nsm_config import (
    NsmTypeConfig,
    backfill_cot_nsm_config_comments,
    build_nsm_config_preview_rows,
    config_dict_from_spec,
    cot_slug_for_content_type,
    format_nsm_config_comment_yaml,
    resolve_nsm_config_for_cot,
    sync_cot_nsm_config_comments,
    sync_cot_nsm_config_comments_for_slugs,
)
from netbox_nsm.objects.type_config_specs import TYPECONFIG_UI_SPECS

__all__ = (
    "backfill_cot_nsm_config_comments",
    "build_all_type_configs_preview_rows",
    "build_type_config_export_data",
    "build_type_config_preview_rows",
    "content_type_export_ref",
    "cot_slug_for_content_type",
    "export_all_type_configs_yaml",
    "export_type_config_yaml",
    "format_all_type_configs_comment_yaml",
    "format_type_config_comment_yaml",
    "format_type_config_comment_yaml_for_spec",
    "format_type_config_comment_yaml_for_config",
    "sync_cot_nsm_config_comments",
    "sync_cot_nsm_config_comments_for_slugs",
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
        "display_template": config.display_template or "{name}",
    }


def format_type_config_comment_yaml(
    sort_order: int,
    display_template: str,
) -> str:
    """Return canonical ``nsm_config`` YAML (legacy two-arg helper)."""
    return format_nsm_config_comment_yaml(
        {
            "sort_order": sort_order,
            "display_template": display_template or "{name}",
        }
    )


def format_type_config_comment_yaml_for_spec(spec: dict) -> str:
    """YAML section for a ``TYPECONFIG_*`` spec dict."""
    return format_nsm_config_comment_yaml(config_dict_from_spec(spec))


def format_type_config_comment_yaml_for_config(config: NsmTypeConfig) -> str:
    """YAML section reflecting resolved Object Config."""
    return format_nsm_config_comment_yaml(
        {
            "sort_order": config.sort_order,
            "display_template": config.display_template,
        }
    )


def format_all_type_configs_comment_yaml() -> str:
    """All nine UI Object Config definitions from ``TYPECONFIG_UI_SPECS``."""
    sections = [
        format_type_config_comment_yaml_for_spec(spec).rstrip()
        for spec in sorted(
            TYPECONFIG_UI_SPECS,
            key=lambda item: (item["sort_order"], item["label"]),
        )
    ]
    return "\n\n".join(sections) + "\n"


def _resolved_ui_configs() -> list[NsmTypeConfig]:
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return []

    configs: list[NsmTypeConfig] = []
    for spec in TYPECONFIG_UI_SPECS:
        cot = CustomObjectType.objects.filter(slug=spec["slug"]).first()
        if not cot:
            continue
        resolved = resolve_nsm_config_for_cot(cot)
        if resolved:
            configs.append(resolved)
    return sorted(configs, key=lambda item: (item.sort_order, item.name))


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
            "display_template": cfg.display_template or "{name}",
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
