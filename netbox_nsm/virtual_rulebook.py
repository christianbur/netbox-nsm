"""Virtual read-only rulebook entry for the aggregated all-rules overview."""

from __future__ import annotations

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox_nsm.models import Rule


def all_rules_count() -> int:
    return Rule.objects.count()


__all__ = (
    "ALL_RULES_CHANGELOG_URL_NAME",
    "ALL_RULES_CONTACTS_URL_NAME",
    "ALL_RULES_JOURNAL_URL_NAME",
    "ALL_RULES_RULEBOOK_URL_NAME",
    "ALL_RULES_RULES_URL_NAME",
    "VIRTUAL_ALL_RULES_PK",
    "VirtualAllRulesRulebook",
    "build_virtual_all_rules_row",
    "is_virtual_all_rules_rulebook",
)

VIRTUAL_ALL_RULES_PK = 0

ALL_RULES_RULEBOOK_URL_NAME = "all_rules_rulebook"
ALL_RULES_RULES_URL_NAME = "all_rules_rules"
ALL_RULES_CONTACTS_URL_NAME = "all_rules_contacts"
ALL_RULES_JOURNAL_URL_NAME = "all_rules_journal"
ALL_RULES_CHANGELOG_URL_NAME = "all_rules_changelog"


def is_virtual_all_rules_rulebook(record) -> bool:
    if getattr(record, "_is_virtual_all_rules", False):
        return True
    return getattr(record, "pk", None) == VIRTUAL_ALL_RULES_PK


class _EmptyRelatedManager:
    def all(self):
        return []


class _VirtualRulebookMeta:
    """
    Shim mimicking ``django.db.models.options.Options`` for plugin template panels.

    NetBox plugins resolve ContentType via ``_meta.model`` / ``_meta.concrete_model``
    (e.g. netbox_custom_objects, netbox_nsm security panel). Delegate everything else
    to the real Rulebook model meta.
    """

    def __init__(self):
        from netbox_nsm.models import Rulebook

        self._delegate = Rulebook._meta

    @property
    def model(self):
        return self._delegate.model

    @property
    def concrete_model(self):
        return self._delegate.concrete_model

    def __getattr__(self, name):
        return getattr(self._delegate, name)


class VirtualAllRulesRulebook:
    """Synthetic rulebook shown first on the rulebook list (no DB row)."""

    _is_virtual_all_rules = True
    _meta = _VirtualRulebookMeta()
    pk = VIRTUAL_ALL_RULES_PK
    id = VIRTUAL_ALL_RULES_PK

    def __init__(self, *, rule_count: int | None = None):
        self.rule_count = rule_count if rule_count is not None else all_rules_count()
        self.name = str(_("All Rules"))
        self.status = "virtual"
        self.parent = None
        self.platform = None
        self.mgmt_url = ""
        self.rule_comment_template = ""
        self.comments = ""
        self.custom_field_data = {}
        self.description = str(_("Read-only view across all policy rulebooks."))
        self.matrix_tab_enabled = False
        self._hierarchy_depth = 0
        self.assignments = _EmptyRelatedManager()
        self.tags = _EmptyRelatedManager()

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"VirtualAllRulesRulebook(pk={self.pk!r}, name={self.name!r})"

    def get_absolute_url(self):
        return reverse(f"plugins:netbox_nsm:{ALL_RULES_RULEBOOK_URL_NAME}")

    def get_rules_tab_url(self):
        return reverse(f"plugins:netbox_nsm:{ALL_RULES_RULES_URL_NAME}")

    @property
    def is_virtual_all_rules(self):
        return True

    def get_rulebook_type_display(self):
        return str(_("Policy (aggregated)"))

    def hierarchy_depth(self):
        return 0


def build_virtual_all_rules_row(
    *, rule_count: int | None = None
) -> VirtualAllRulesRulebook:
    return VirtualAllRulesRulebook(rule_count=rule_count)
