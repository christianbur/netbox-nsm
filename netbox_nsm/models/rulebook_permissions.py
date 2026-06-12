"""Permission anchors for virtual COT rulebooks and their host assignments."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from netbox_nsm.models.cot_rulebook_assignment import CotRulebookAssignment

__all__ = (
    "Rulebook",
    "RulebookAssignment",
)


class Rulebook(models.Model):
    """Permission anchor for COT-backed rulebooks (no database table)."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("view_rulebook", "Can view rulebooks"),
            ("add_rulebook", "Can add rulebooks"),
        ]
        verbose_name = _("Rulebook")
        verbose_name_plural = _("Rulebooks")


class RulebookAssignment(CotRulebookAssignment):
    """Proxy model so assignment permission codenames resolve to ``rulebookassignment``."""

    class Meta:
        proxy = True
        default_permissions = ()
        permissions = [
            ("view_rulebookassignment", "Can view rulebook assignments"),
            ("add_rulebookassignment", "Can add rulebook assignments"),
            ("change_rulebookassignment", "Can change rulebook assignments"),
            ("delete_rulebookassignment", "Can delete rulebook assignments"),
        ]
        verbose_name = _("Rulebook Assignment")
        verbose_name_plural = _("Rulebook Assignments")
