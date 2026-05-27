from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel
from netbox.search import SearchIndex, register_search

__all__ = ("SecurityObject", "SecurityObjectIndex")


class SecurityObject(PrimaryModel):
    custom_type = models.ForeignKey(
        to="netbox_nsm.SecurityObjectType",
        on_delete=models.PROTECT,
        related_name="custom_objects",
    )
    name = models.CharField(max_length=100)
    field_data = models.JSONField(
        blank=True,
        default=dict,
        help_text=_("Dynamic field values defined by the custom type."),
    )
    table_data = models.JSONField(
        blank=True,
        default=list,
        help_text=_("Key/value table rows: [{\"key\": \"...\", \"value\": \"...\"}]"),
    )

    class Meta:
        verbose_name = _("Custom Object")
        verbose_name_plural = _("Custom Objects")
        ordering = ("custom_type", "name")
        constraints = (
            models.UniqueConstraint(
                fields=("custom_type", "name"),
                name="netbox_nsm_securityobject_unique_type_name",
            ),
        )

    def __str__(self):
        return f"{self.custom_type}: {self.name}"

    def render_display(self):
        """Return display string using custom_type.display_template if set."""
        tmpl = getattr(self.custom_type, "display_template", "") or ""
        if tmpl:
            try:
                ctx = {"name": self.name, **(self.field_data or {})}
                return tmpl.format_map(ctx)
            except (KeyError, ValueError):
                pass
        return self.name

    def render_comments(self):
        """Render comments with {name} / field_data key substitution."""
        raw = getattr(self, "comments", "") or ""
        if not raw:
            return ""
        try:
            ctx = {
                "name": self.name,
                "description": getattr(self, "description", ""),
                **(self.field_data or {}),
            }
            return raw.format_map(ctx)
        except (KeyError, ValueError):
            return raw

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:objectcustom", args=[self.pk])


@register_search
class SecurityObjectIndex(SearchIndex):
    model = SecurityObject
    fields = (
        ("name", 200),
        ("description", 500),
    )
