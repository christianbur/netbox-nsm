from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

__all__ = ("CotRulebook",)


class CotRulebook(models.Model):
    """Parent/child hierarchy for deployed COT rulebooks (``nsm_rb_*``)."""

    slug = models.SlugField(
        max_length=100,
        primary_key=True,
        verbose_name=_("Rulebook slug"),
        help_text=_("Slug of the deployed COT rulebook (nsm_rb_<name>)."),
    )
    parent_slug = models.SlugField(
        max_length=100,
        blank=True,
        default="",
        verbose_name=_("Parent rulebook slug"),
        help_text=_("Optional parent rulebook slug for hierarchical grouping."),
    )
    matrix_tab_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Matrix tab enabled"),
        help_text=_(
            "When enabled, show the Matrix tab for rulebooks with source and "
            "destination zone columns."
        ),
    )
    row_group_by_col_id = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name=_("Grouped rows"),
        help_text=_(
            "Rules tab column used for vertical side-tab row grouping (col_id "
            "from the rules table layout)."
        ),
    )

    class Meta:
        verbose_name = _("COT Rulebook")
        verbose_name_plural = _("COT Rulebooks")

    def __str__(self):
        return self.slug

    def clean(self):
        from netbox_nsm.rulebooks.cot_hierarchy import validate_cot_parent_slug

        parent = (self.parent_slug or "").strip() or None
        error = validate_cot_parent_slug(self.slug, parent)
        if error:
            raise ValidationError({"parent_slug": error})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
