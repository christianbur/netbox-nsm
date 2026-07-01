"""Tab navigation for COT-backed rulebooks."""

from __future__ import annotations

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox_nsm.rulebooks.permissions import can_view_rulebook
from netbox_nsm.rulebooks.rules_tab import rules_tab_badge_for_object
from utilities.views import ViewTab

__all__ = ("build_virtual_cot_rulebook_tabs",)

def _cot_matrix_tab_visible(instance) -> bool:
    return bool(getattr(instance, "matrix_tab_enabled", False))


_COT_TAB_SPECS = (
    {
        "key": "rules",
        "view_key": "table",
        "url_name": "cot_rulebook_rules",
        "view_tab": ViewTab(
            label=_("Rules"),
            badge=rules_tab_badge_for_object,
            weight=100,
        ),
        "requires_rulebook_view": True,
    },
    {
        "key": "matrix",
        "view_key": "matrix",
        "url_name": "cot_rulebook_matrix",
        "view_tab": ViewTab(
            label=_("Matrix"),
            weight=300,
            hide_if_empty=True,
            visible=_cot_matrix_tab_visible,
        ),
        "requires_rulebook_view": True,
    },
    {
        "key": "changelog",
        "url_name": "cot_rulebook_changelog",
        "view_tab": ViewTab(
            label=_("Changelog"),
            permission="core.view_objectchange",
            weight=10000,
        ),
    },
)


def build_virtual_cot_rulebook_tabs(
    request, instance, *, active_key: str | None = None
) -> list[dict]:
    from netbox_nsm.rulebooks.views.registry import resolve_rulebook_view_keys

    user = request.user
    cot = getattr(instance, "cot", None)
    enabled_view_keys = resolve_rulebook_view_keys(cot) if cot is not None else set()
    tabs: list[dict] = []
    for spec in _COT_TAB_SPECS:
        view_tab = spec["view_tab"]
        if spec.get("requires_rulebook_view"):
            if cot is None or not can_view_rulebook(user, cot):
                continue
            view_key = spec.get("view_key")
            if view_key is not None and view_key not in enabled_view_keys:
                continue
        elif view_tab.permission and not user.has_perm(view_tab.permission):
            continue
        rendered = view_tab.render(instance)
        if rendered is None:
            continue
        tabs.append(
            {
                "key": spec["key"],
                "url": reverse(
                    f"plugins:netbox_nsm:{spec['url_name']}",
                    kwargs={"slug": instance.slug},
                ),
                "label": rendered["label"],
                "badge": rendered["badge"],
                "weight": rendered["weight"],
                "is_active": active_key == spec["key"],
            }
        )
    return sorted(tabs, key=lambda row: row["weight"])
