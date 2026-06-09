from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel

__all__ = (
    "MatchingClassChoices",
    "PANEL_LINKABLE_DISABLED",
    "TypeConfig",
)

# Sentinel stored in panel_linkable_types to represent legacy panel_linkable=False.
PANEL_LINKABLE_DISABLED = 0


class MatchingClassChoices(models.TextChoices):
    ADDRESS = "address", _("Address")
    ZONE = "zone", _("Zone")
    LABEL_SCOPE = "label-scope", _("Label-Scope")
    LABEL = "label", _("Label")
    TRUST = "trust", _("Trust")
    SERVICE = "service", _("Service")
    ACTION = "action", _("Action")
    INFO = "info", _("Info")
    USER = "user", _("User")
    APPLICATION = "application", _("Application")
    GROUP = "group", _("Group")
    OTHER = "other", _("Other")


class TypeConfig(NetBoxModel):
    """Per-ContentType configuration for NSM panels, rulebooks, and display."""

    name = models.CharField(
        max_length=100,
        verbose_name=_("Name"),
        help_text=_(
            "Display name used as column header and type label throughout NSM."
        ),
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
    allow_virtual_groups = models.BooleanField(
        default=False,
        verbose_name=_("Allow Virtual Groups"),
        help_text=_(
            "Allows building virtual groups (AND-linking) for this type "
            "in the panel and rule editor. Multiple groups are linked with OR."
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
    panel_linkable_types = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Linkable in panel"),
        help_text=_(
            "NetBox object types that may assign this NSM type via + Assign in the "
            "Security Panel. Leave empty to allow all object types."
        ),
    )

    class Meta:
        verbose_name = _("Type Config")
        verbose_name_plural = _("Type Configs")
        ordering = (
            "name",
            "content_type__app_label",
            "content_type__model",
            "matching_class",
        )
        unique_together = [("content_type", "matching_class")]

    @classmethod
    def queryset_panel_linkable(cls):
        """TypeConfigs that may appear as Object B in the Security Panel assign picker."""
        return cls.objects.exclude(panel_linkable_types=[PANEL_LINKABLE_DISABLED])

    @classmethod
    def queryset_assignable_from(cls, assigner_content_type_id):
        """TypeConfigs assignable from a given NetBox object type (Object A)."""
        from django.db.models import Q

        return cls.queryset_panel_linkable().filter(
            Q(panel_linkable_types=[])
            | Q(panel_linkable_types__contains=[assigner_content_type_id])
        )

    def is_panel_linkable_disabled(self) -> bool:
        return self.panel_linkable_types == [PANEL_LINKABLE_DISABLED]

    def is_assignable_from_content_type(self, content_type_id) -> bool:
        if self.is_panel_linkable_disabled():
            return False
        allowed = self.panel_linkable_types or []
        if not allowed:
            return True
        return int(content_type_id) in allowed

    def panel_linkable_type_labels(self) -> list[str]:
        """Human-readable labels for restricted assigner object types."""
        allowed = [
            int(pk)
            for pk in (self.panel_linkable_types or [])
            if int(pk) != PANEL_LINKABLE_DISABLED
        ]
        if not allowed:
            return []
        labels: list[str] = []
        for ct in ContentType.objects.filter(pk__in=allowed).order_by(
            "app_label", "model"
        ):
            mc = ct.model_class()
            if mc:
                labels.append(str(mc._meta.verbose_name).title())
            else:
                labels.append(ct.model.replace("_", " ").title())
        return labels

    @property
    def content_type_label(self):
        """Human-readable NetBox model name for UI (e.g. 'Zone')."""
        if not self.content_type_id:
            return ""
        mc = self.content_type.model_class()
        if mc:
            vn = mc._meta.verbose_name
            if vn:
                return str(vn).title()
            return mc._meta.model_name.replace("_", " ").title()
        return self.content_type.model.replace("_", " ").title()

    @staticmethod
    def _label_dedup_key(label: str) -> str:
        """Normalize labels so Zone / Zones / zone compare equal."""
        s = (label or "").strip().lower()
        if len(s) > 3 and s.endswith("es"):
            return s[:-2]
        if len(s) > 2 and s.endswith("s"):
            return s[:-1]
        return s

    @property
    def type_line_subtitle(self) -> str:
        """
        Secondary type line label; empty when it would repeat the primary title.
        """
        name = (self.name or "").strip()
        primary = name or self.content_type_label or ""
        pkey = self._label_dedup_key(primary)
        bits: list[str] = []
        candidates: list[str] = []
        if name:
            candidates.append(self.content_type_label)
        if self.matching_class:
            candidates.append(self.get_matching_class_display())
        for label in candidates:
            label = (label or "").strip()
            if not label:
                continue
            lkey = self._label_dedup_key(label)
            if lkey == pkey:
                continue
            if any(self._label_dedup_key(b) == lkey for b in bits):
                continue
            bits.append(label)
        return " · ".join(bits)

    @property
    def type_line_subtitle_parts(self) -> list[str]:
        """Subtitle segments for pill display on the rulebook detail page."""
        sub = self.type_line_subtitle
        if not sub:
            return []
        return [part.strip() for part in sub.split(" · ") if part.strip()]

    @property
    def type_line_kind_parts(self) -> list[str]:
        """Kind-column badges (matching class + meta), deduplicated."""
        parts: list[str] = []
        if self.matching_class:
            mc_label = (self.get_matching_class_display() or "").strip()
            if mc_label:
                parts.append(mc_label)
        for label in self.type_line_subtitle_parts:
            label = (label or "").strip()
            if not label:
                continue
            if any(
                self._label_dedup_key(label) == self._label_dedup_key(p) for p in parts
            ):
                continue
            parts.append(label)
        return parts

    @property
    def matching_class_icon(self):
        icons = {
            MatchingClassChoices.ADDRESS: "mdi-ip-network-outline",
            MatchingClassChoices.ZONE: "mdi-map-marker-radius-outline",
            MatchingClassChoices.SERVICE: "mdi-cog-outline",
            MatchingClassChoices.ACTION: "mdi-play-circle-outline",
            MatchingClassChoices.INFO: "mdi-information-outline",
            MatchingClassChoices.USER: "mdi-account-outline",
            MatchingClassChoices.APPLICATION: "mdi-application-outline",
            MatchingClassChoices.GROUP: "mdi-account-group-outline",
            MatchingClassChoices.LABEL: "mdi-label-outline",
            MatchingClassChoices.LABEL_SCOPE: "mdi-label-multiple-outline",
            MatchingClassChoices.TRUST: "mdi-shield-check-outline",
        }
        return icons.get(self.matching_class, "mdi-cube-outline")

    @property
    def matching_class_css_slug(self):
        """Safe slug for nsm-rb-mc-* CSS classes (e.g. label-scope)."""
        mc = (self.matching_class or "").strip()
        return mc or MatchingClassChoices.OTHER

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
        return reverse("plugins:netbox_nsm:typeconfig", args=[self.pk])

    def serialize_object(self, exclude=None):
        data = super().serialize_object(exclude=exclude)
        data["panel_linkable_types"] = _serialize_type_config_panel_linkable_types(
            self.panel_linkable_types
        )
        return data


def _serialize_type_config_panel_linkable_types(type_ids):
    ids = type_ids or []
    if ids == [PANEL_LINKABLE_DISABLED]:
        return {"__disabled__": True}
    return {str(int(pk)): int(pk) for pk in ids if int(pk) != PANEL_LINKABLE_DISABLED}
