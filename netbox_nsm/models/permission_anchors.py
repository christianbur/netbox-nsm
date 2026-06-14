"""Unmanaged models used only as Django permission anchors."""

from django.db import models
from django.utils.translation import gettext_lazy as _

__all__ = ("TypeConfig",)


class TypeConfig(models.Model):
    """Permission anchor for Object Config / ``nsm_config`` (no database table)."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("view_typeconfig", "Can view object configs"),
            ("add_typeconfig", "Can add object configs"),
            ("change_typeconfig", "Can change object configs"),
            ("delete_typeconfig", "Can delete object configs"),
        ]
        verbose_name = _("Object Config")
        verbose_name_plural = _("Object Configs")
