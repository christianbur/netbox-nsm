"""Tab navigation for COT-backed rulebooks."""

from __future__ import annotations

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox_nsm.rulebooks.rules_tab_base import rules_tab_badge_for_object
from utilities.views import ViewTab

__all__ = ("build_virtual_cot_rulebook_tabs",)

def _cot_matrix_tab_visible(instance) -> bool:
    return bool(getattr(instance, "matrix_tab_enabled", False))


_COT_TAB_SPECS = (
    {
        "key": "rules",
        "url_name": "cot_rulebook_rules",
        "view_tab": ViewTab(
            label=_("Rules"),
            badge=rules_tab_badge_for_object,
            permission="netbox_nsm.view_rulebook",
            weight=100,
        ),
    },
    {
        "key": "matrix",
        "url_name": "cot_rulebook_matrix",
        "view_tab": ViewTab(
            label=_("Matrix"),
            permission="netbox_nsm.view_rulebook",
            weight=300,
            hide_if_empty=True,
            visible=_cot_matrix_tab_visible,
        ),
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
    user = request.user
    tabs: list[dict] = []
    for spec in _COT_TAB_SPECS:
        view_tab = spec["view_tab"]
        if view_tab.permission and not user.has_perm(view_tab.permission):
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
