"""Rule-row proxy operations on COT rulebooks (add / del / clone / edit)."""

from netbox_nsm.rulebooks.proxy.rule_rows import (
    can_edit_rules,
    rule_add_url,
    rule_bulk_import_url,
    rule_delete_url,
    rule_edit_url,
    rulebook_clone_initial,
    rulebook_clone_url,
)

__all__ = (
    "can_edit_rules",
    "rule_add_url",
    "rule_bulk_import_url",
    "rule_delete_url",
    "rule_edit_url",
    "rulebook_clone_initial",
    "rulebook_clone_url",
)
