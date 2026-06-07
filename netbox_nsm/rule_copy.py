"""Clone a security rule into the add form (metadata + assignments, not name/index)."""

from __future__ import annotations

from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from utilities.querydict import prepare_cloned_fields

from netbox_nsm.models import Rule

__all__ = (
    "COPY_RULE_PARAM",
    "rule_clone_add_url",
)

COPY_RULE_PARAM = "copy_from"
CLONE_LABEL = _("Clone")


def rule_clone_add_url(rule: Rule | int, *, return_url: str | None = None) -> str:
    """Build the rule add URL pre-filled from *rule* (name omitted; index set on open)."""
    if not isinstance(rule, Rule):
        rule = Rule.objects.get(pk=rule)
    params = prepare_cloned_fields(rule)
    params[COPY_RULE_PARAM] = str(rule.pk)
    if return_url:
        params["return_url"] = return_url
    base = reverse("plugins:netbox_nsm:rule_add")
    encoded = params.urlencode()
    return f"{base}?{encoded}" if encoded else base
