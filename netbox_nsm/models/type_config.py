from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel

from netbox_nsm.core.type_kind import type_config_css_slug, type_config_icon

__all__ = (
    "PANEL_LINKABLE_DISABLED",
    "TypeConfig",
)

# Sentinel stored in panel_linkable_types to represent legacy panel_linkable=False.
PANEL_LINKABLE_DISABLED = 0


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
    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Sort order"),
        help_text=_(
            "Display order in the Object Config list and other NSM type pickers "
            "(lower values appear first)."
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
        verbose_name = _("Object Config")
        verbose_name_plural = _("Object Configs")
        ordering = (
            "sort_order",
            "name",
            "content_type__app_label",
            "content_type__model",
        )
        constraints = [
            models.UniqueConstraint(
                fields=["content_type"],
                name="netbox_nsm_typeconfig_content_type_uniq",
            ),
        ]

    @classmethod
    def queryset_for_settings_list(cls):
        """TypeConfigs shown in the NSM Object Config management list."""
        from netbox_nsm.objects.type_config_specs import (
            TYPECONFIG_LIST_EXCLUDED_SLUGS,
            content_type_ids_for_cot_slugs,
        )

        excluded_ct_ids = content_type_ids_for_cot_slugs(TYPECONFIG_LIST_EXCLUDED_SLUGS)
        qs = cls.objects.all()
        if excluded_ct_ids:
            qs = qs.exclude(content_type_id__in=excluded_ct_ids)
        return qs

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
        if name:
            label = (self.content_type_label or "").strip()
            if label:
                lkey = self._label_dedup_key(label)
                if lkey != pkey and not any(
                    self._label_dedup_key(b) == lkey for b in bits
                ):
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
        """Kind-column badges (meta), deduplicated."""
        parts: list[str] = []
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
    def type_css_slug(self):
        """Safe slug for nsm-rb-mc-* CSS classes (e.g. label-scope)."""
        return type_config_css_slug(self)

    @property
    def type_icon(self):
        return type_config_icon(self)

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
            return f"{app_label} › {model_label}"
        return f"{self.content_type.app_label} | {self.content_type.model}"

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
