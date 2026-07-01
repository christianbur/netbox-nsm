"""Virtual rulebook rows backed by Custom Object Type rulebooks."""

from __future__ import annotations

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox_nsm.rulebooks.matrix.cot_matrix_tab_context import (
    cot_rulebook_matrix_capable,
    cot_rulebook_matrix_enabled,
)
from netbox_nsm.rulebooks.registry import cot_rulebook_instance_count
from netbox_nsm.rulebooks.virtual_all import _EmptyRelatedManager, _VirtualRulebookMeta

__all__ = (
    "COT_RULEBOOK_CHANGELOG_URL_NAME",
    "COT_RULEBOOK_MATRIX_URL_NAME",
    "COT_RULEBOOK_RULES_URL_NAME",
    "COT_RULEBOOK_URL_NAME",
    "VirtualCotRulebook",
    "build_virtual_cot_rulebook_row",
    "is_virtual_cot_rulebook",
)

COT_RULEBOOK_URL_NAME = "cot_rulebook"
COT_RULEBOOK_RULES_URL_NAME = "cot_rulebook_rules"
COT_RULEBOOK_MATRIX_URL_NAME = "cot_rulebook_matrix"
COT_RULEBOOK_CHANGELOG_URL_NAME = "cot_rulebook_changelog"


def is_virtual_cot_rulebook(record) -> bool:
    return getattr(record, "_is_virtual_cot_rulebook", False)


class VirtualCotRulebook:
    """Synthetic list/detail object for a deployed ``nsm_rb_<name>`` COT."""

    _is_virtual_cot_rulebook = True
    _meta = _VirtualRulebookMeta()

    def __init__(self, cot, *, rule_count: int | None = None):
        self.cot = cot
        self.cot_pk = cot.pk
        self.slug = cot.slug
        self.pk = f"cot:{cot.slug}"
        self.id = self.pk
        self.name = cot.verbose_name or cot.name
        self.status = "active"
        self.parent = None
        self.parent_slug = ""
        self.parent_id = None
        self.platform = None
        self.mgmt_url = ""
        self.rule_comment_template = ""
        self.comments = ""
        self.custom_field_data = {}
        self.description = cot.description or ""
        self.matrix_tab_capable = cot_rulebook_matrix_capable(cot)
        self.matrix_tab_enabled = cot_rulebook_matrix_enabled(cot)
        self.nsm_list_depth = 0
        self.rule_count = (
            rule_count if rule_count is not None else cot_rulebook_instance_count(cot)
        )
        self.assignments = _EmptyRelatedManager()
        self.tags = _EmptyRelatedManager()

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"VirtualCotRulebook(slug={self.slug!r}, name={self.name!r})"

    def get_absolute_url(self):
        return reverse(
            f"plugins:netbox_nsm:{COT_RULEBOOK_URL_NAME}",
            kwargs={"slug": self.slug},
        )

    def get_rules_tab_url(self):
        return reverse(
            f"plugins:netbox_nsm:{COT_RULEBOOK_RULES_URL_NAME}",
            kwargs={"slug": self.slug},
        )

    def get_matrix_tab_url(self):
        return reverse(
            f"plugins:netbox_nsm:{COT_RULEBOOK_MATRIX_URL_NAME}",
            kwargs={"slug": self.slug},
        )

    def get_changelog_tab_url(self):
        return reverse(
            f"plugins:netbox_nsm:{COT_RULEBOOK_CHANGELOG_URL_NAME}",
            kwargs={"slug": self.slug},
        )

    def get_rulebook_type_display(self):
        return str(_("Rulebook"))

    def hierarchy_depth(self):
        from netbox_nsm.rulebooks.hierarchy import rulebook_list_depth

        return rulebook_list_depth(self)


def build_virtual_cot_rulebook_row(cot, *, rule_count: int | None = None) -> VirtualCotRulebook:
    return VirtualCotRulebook(cot, rule_count=rule_count)
