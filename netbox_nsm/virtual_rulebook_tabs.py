"""Tab navigation for the virtual All Rules rulebook (mirrors rulebook ViewTabs)."""

from __future__ import annotations

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from utilities.views import ViewTab

__all__ = (
    "PRIMARY_TAB_KEY",
    "PRIMARY_TAB_LABEL",
    "build_virtual_rulebook_tabs",
)

PRIMARY_TAB_KEY = "detail"
PRIMARY_TAB_LABEL = _("Rulebook")

# Labels, weights, and permissions aligned with RulebookRulesGridView and NetBox
# feature tabs (contacts, journal, changelog) on rulebooks.
_VIRTUAL_TAB_SPECS = (
    {
        "key": "rules",
        "url_name": "all_rules_rules",
        "view_tab": ViewTab(
            label=_("Rules"),
            badge=lambda obj: getattr(obj, "rule_count", None) or None,
            permission="netbox_nsm.view_rulebook",
            weight=100,
        ),
    },
    {
        "key": "contacts",
        "url_name": "all_rules_contacts",
        "view_tab": ViewTab(
            label=_("Contacts"),
            badge=lambda obj: 0,
            permission="tenancy.view_contactassignment",
            weight=5000,
        ),
    },
    {
        "key": "journal",
        "url_name": "all_rules_journal",
        "view_tab": ViewTab(
            label=_("Journal"),
            badge=lambda obj: 0,
            permission="extras.view_journalentry",
            weight=9000,
        ),
    },
    {
        "key": "changelog",
        "url_name": "all_rules_changelog",
        "view_tab": ViewTab(
            label=_("Changelog"),
            permission="core.view_objectchange",
            weight=10000,
        ),
    },
)


def build_virtual_rulebook_tabs(
    request, instance, *, active_key: str | None = None
) -> list[dict]:
    """Return sorted tab dicts for the virtual All Rules rulebook pages."""
    user = request.user
    tabs: list[dict] = []
    for spec in _VIRTUAL_TAB_SPECS:
        view_tab = spec["view_tab"]
        if view_tab.permission and not user.has_perm(view_tab.permission):
            continue
        rendered = view_tab.render(instance)
        if rendered is None:
            continue
        tabs.append(
            {
                "key": spec["key"],
                "url": reverse(f"plugins:netbox_nsm:{spec['url_name']}"),
                "label": rendered["label"],
                "badge": rendered["badge"],
                "weight": rendered["weight"],
                "is_active": active_key == spec["key"],
            }
        )
    return sorted(tabs, key=lambda row: row["weight"])
