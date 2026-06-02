from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel

__all__ = ("MatchingClassChoices", "TypeConfig")


class MatchingClassChoices(models.TextChoices):
    ADDRESS = "address", _("Address")
    ZONE = "zone", _("Zone")
    LABEL_SCOPE = "label-scope", _("Label-Scope")
    LABEL = "label", _("Label")
    TRUST = "trust", _("Trust")
    SERVICE = "service", _("Service")
    ACTION = "action", _("Action")
    USER = "user", _("User")
    APPLICATION = "application", _("Application")
    GROUP = "group", _("Group")
    OTHER = "other", _("Other")


class TypeConfig(NetBoxModel):
    """Global per-ContentType configuration.

    Defines how a NetBox object type behaves in NSM: its matching class
    (used to auto-derive rulebook matching strategy), display template,
    and which placements it is allowed to appear in.
    """

    name = models.CharField(
        max_length=100,
        verbose_name=_("Name"),
        help_text=_("Display name used as column header and type label throughout NSM."),
    )
    content_type = models.ForeignKey(
        to="contenttypes.ContentType",
        on_delete=models.CASCADE,
        related_name="nsm_matching_configs",
        verbose_name=_("Object Type"),
    )
    matching_class = models.CharField(
        max_length=20,
        choices=MatchingClassChoices.choices,
        blank=True,
        default="",
        verbose_name=_("Matching Class"),
        help_text=_(
            "Semantic category of this type. Used to automatically derive the "
            "matching strategy of a Rulebook (e.g. 'label', 'zone', 'address')."
        ),
    )
    display_template = models.CharField(
        max_length=255,
        blank=True,
        default="{name}",
        verbose_name=_("Display Template"),
        help_text=_(
            "Format string used to render an object's display name. "
            "Field names in curly braces are substituted (e.g. '{name} ({protocol})')."
        ),
    )
    allowed_placements = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Allowed Placements"),
        help_text=_(
            "UI hint: list of placements this type may appear in. "
            'Example: ["source", "destination"] or ["fixed"]. '
            "Leave empty to allow all placements."
        ),
    )
    inherit_links = models.BooleanField(
        default=False,
        verbose_name=_("Inherit from parent"),
        help_text=_(
            "When enabled, Security Panel shows NSM links of the containing Prefix "
            "on child objects (IP Address, IP Range, sub-Prefix)."
        ),
    )
    inherit_stop_on_own = models.BooleanField(
        default=False,
        verbose_name=_("Stop inheritance if own link present"),
        help_text=_(
            "If the child object already has its own direct NSM link of the same "
            "type, inherited links of that type are suppressed."
        ),
    )
    panel_linkable = models.BooleanField(
        default=True,
        verbose_name=_("Linkable in panel"),
        help_text=_(
            "If enabled, objects of this type can be linked from the NSM Security Panel."
        ),
    )

    class Meta:
        verbose_name = _("Type Config")
        verbose_name_plural = _("Type Configs")
        ordering = ("content_type__app_label", "content_type__model", "matching_class")
        unique_together = [("content_type", "matching_class")]

    def __str__(self):
        if self.name:
            return self.name
        if not self.content_type_id:
            return f"TypeConfig(#{self.pk})"
        mc = self.content_type.model_class()
        if mc:
            app_label = getattr(
                mc._meta.app_config, "verbose_name", self.content_type.app_label
            )
            model_label = mc._meta.verbose_name.title()
            base = f"{app_label} › {model_label}"
        else:
            base = f"{self.content_type.app_label} | {self.content_type.model}"
        if self.matching_class:
            return f"{base} ({self.matching_class})"
        return base

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:typeconfig_edit", args=[self.pk])
