from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel

__all__ = ("NSMTypeConfig",)


class NSMTypeConfig(NetBoxModel):
    """Per-ContentType configuration owned by netbox_nsm.

    Maps any NetBox object type (ContentType) to NSM metadata:
    display_template, order_id, and security areas.
    """

    content_type = models.ForeignKey(
        to="contenttypes.ContentType",
        on_delete=models.CASCADE,
        related_name="nsm_type_configs",
        unique=True,
    )
    areas = models.ManyToManyField(
        to="netbox_nsm.SecurityArea",
        related_name="type_configs",
        blank=True,
        verbose_name=_("Areas"),
        help_text=_("Security areas in which this type appears."),
    )
    display_template = models.CharField(
        max_length=255,
        blank=True,
        default="{name}",
        help_text=_(
            "Format string used to render an object's display name. "
            "Field names in curly braces are substituted (e.g. '{name} ({protocol})')."
        ),
    )
    order_id = models.PositiveIntegerField(
        default=100,
        help_text=_("Sort order of this type within its NSM section."),
    )
    allow_virtual_groups = models.BooleanField(
        default=False,
        verbose_name=_("Allow Virtual Groups"),
        help_text=_(
            "Allows building virtual groups (AND-linking) for this type "
            "in the panel and rule editor. Multiple groups are linked with OR."
        ),
    )

    class Meta:
        verbose_name = _("NSM Type Config")
        verbose_name_plural = _("NSM Type Configs")
        ordering = ("order_id", "content_type__app_label", "content_type__model")

    def __str__(self):
        if not self.content_type_id:
            return f"NSMTypeConfig(#{self.pk})"
        mc = self.content_type.model_class()
        if mc:
            app_label = getattr(mc._meta.app_config, "verbose_name", self.content_type.app_label)
            model_label = mc._meta.verbose_name.title()
            return f"{app_label} › {model_label}"
        return f"{self.content_type.app_label} | {self.content_type.model}"

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:nsmtypeconfig_edit", args=[self.pk])
