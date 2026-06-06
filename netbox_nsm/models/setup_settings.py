from django.db import models
from django.utils.translation import gettext_lazy as _

__all__ = ("NsmUiSettings",)

DEFAULT_MENU_LABEL = "Security"
DEFAULT_PANEL_LABEL = "Security"


class NsmUiSettings(models.Model):
    """Singleton: menu and panel titles configured via Setup."""

    menu_label = models.CharField(
        max_length=100,
        default=DEFAULT_MENU_LABEL,
        verbose_name=_("Menu label"),
        help_text=_("Top-level plugin menu entry in the NetBox sidebar."),
    )
    panel_label = models.CharField(
        max_length=100,
        default=DEFAULT_PANEL_LABEL,
        verbose_name=_("Panel label"),
        help_text=_("Security card title on object detail pages."),
    )

    class Meta:
        verbose_name = _("NSM UI settings")
        verbose_name_plural = _("NSM UI settings")

    def __str__(self):
        return self.menu_label or DEFAULT_MENU_LABEL

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def resolved_panel_label(self) -> str:
        return (self.panel_label or DEFAULT_PANEL_LABEL).strip()
