from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
import re

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
    display_template_override = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text=_("Optional per-object display template. Overrides the type template."),
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
        tmpl = (self.display_template_override or "").strip() or (getattr(self.custom_type, "display_template", "") or "")
        if tmpl:
            try:
                class _SafeDict(dict):
                    def __missing__(self, key):
                        return ""

                field_data = dict(self.field_data or {})
                # Convenience vars: for string fields, expose a "*_initial" placeholder.
                # Example: label_type="Flexible labels" -> label_type_initial="F".
                for key, value in list(field_data.items()):
                    if isinstance(value, str):
                        stripped = value.strip()
                        field_data[f"{key}_initial"] = stripped[:1].upper() if stripped else ""

                # General substring placeholders in templates:
                # {field[0:1]}, {field[:3]}, {field[2:]}, {field[-3:]}, {field[0]}
                # We resolve only placeholders that are actually used in the template.
                token_re = re.compile(r"\{([^{}]+)\}")
                idx_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\[(-?\d+)\]$")
                slice_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\[(-?\d*):(-?\d*)\]$")

                expr_values = {}

                def _resolve_expr(expr):
                    m_idx = idx_re.match(expr)
                    if m_idx:
                        base_key, idx_raw = m_idx.groups()
                        base_val = field_data.get(base_key, "")
                        if isinstance(base_val, str):
                            try:
                                return base_val[int(idx_raw)]
                            except (ValueError, IndexError):
                                return ""
                        return ""

                    m_slice = slice_re.match(expr)
                    if m_slice:
                        base_key, start_raw, end_raw = m_slice.groups()
                        base_val = field_data.get(base_key, "")
                        if isinstance(base_val, str):
                            try:
                                start = int(start_raw) if start_raw != "" else None
                                end = int(end_raw) if end_raw != "" else None
                                return base_val[start:end]
                            except ValueError:
                                return ""
                        return ""

                    return None

                def _replace_expr(match):
                    expr = match.group(1)
                    value = _resolve_expr(expr)
                    if value is None:
                        return match.group(0)

                    key = f"__expr_{len(expr_values)}"
                    expr_values[key] = value
                    return "{" + key + "}"

                safe_tmpl = token_re.sub(_replace_expr, tmpl)

                ctx = _SafeDict({"name": self.name, **field_data, **expr_values})
                return safe_tmpl.format_map(ctx)
            except ValueError:
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
