"""Registry of COT-rulebook display views (Phase C).

A rulebook exposes one or more *views* — currently the **table** (rules tab)
and the **matrix**. Which views appear is driven by metadata
(``nsm_config.rulebook.views``) with a structural default:

* the table view is always available,
* the matrix view is available when ``matrix_tab_enabled`` is set.

This registry is the single source of truth for the rulebook tab navigation
(``virtual_cot_tabs``) and for the ``views/table`` and ``views/matrix``
packages.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _

__all__ = (
    "RulebookViewSpec",
    "RULEBOOK_VIEW_REGISTRY",
    "rulebook_view_keys_registry",
    "raw_rulebook_view_keys",
    "resolve_rulebook_view_keys",
    "iter_enabled_rulebook_views",
)


@dataclass(frozen=True, slots=True)
class RulebookViewSpec:
    key: str  # canonical view key: "table" | "matrix"
    tab_key: str  # tab/url identifier: "rules" | "matrix"
    url_name: str
    label: str
    weight: int
    default_enabled: bool = True


RULEBOOK_VIEW_REGISTRY: tuple[RulebookViewSpec, ...] = (
    RulebookViewSpec("table", "rules", "cot_rulebook_rules", _("Rules"), 100, True),
    RulebookViewSpec(
        "matrix", "matrix", "cot_rulebook_matrix", _("Matrix"), 300, False
    ),
)


def rulebook_view_keys_registry() -> set[str]:
    return {spec.key for spec in RULEBOOK_VIEW_REGISTRY}


def raw_rulebook_view_keys(cot) -> list[str] | None:
    """Return an explicit ``rulebook.views`` list from COT metadata, if present."""
    if cot is None:
        return None
    text = getattr(cot, "comments", "") or ""
    try:
        from netbox_nsm.type_metadata.config import _stored_nsm_config_document
    except Exception:
        return None
    try:
        stored = _stored_nsm_config_document(text)
    except Exception:
        return None
    block = stored.get("rulebook")
    if isinstance(block, dict) and isinstance(block.get("views"), list):
        return [str(value) for value in block["views"]]
    return None


def resolve_rulebook_view_keys(cot) -> set[str]:
    """Return the enabled view keys for *cot* (metadata override or default)."""
    known = rulebook_view_keys_registry()
    explicit = raw_rulebook_view_keys(cot)
    if explicit is not None:
        return {key for key in explicit if key in known}

    keys = {"table"}
    try:
        from netbox_nsm.matrix.cot_matrix_tab_context import cot_rulebook_matrix_enabled

        if cot is not None and cot_rulebook_matrix_enabled(cot):
            keys.add("matrix")
    except Exception:
        pass
    return keys


def iter_enabled_rulebook_views(cot) -> list[RulebookViewSpec]:
    keys = resolve_rulebook_view_keys(cot)
    return [spec for spec in RULEBOOK_VIEW_REGISTRY if spec.key in keys]
