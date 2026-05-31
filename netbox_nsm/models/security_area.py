from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel
from netbox.search import SearchIndex, register_search

__all__ = ("SecurityArea", "SecurityAreaIndex")


class SecurityArea(PrimaryModel):
    sort_order = models.PositiveIntegerField(
        default=100,
        help_text=_("Order for displaying areas in UI tabs/lists (lower comes first)."),
    )
    slug = models.CharField(
        max_length=50,
        unique=True,
        help_text=_(
            "Unique identifier used internally (e.g. 'source', 'destination', 'services')."
        ),
    )
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = _("Security Area")
        verbose_name_plural = _("Security Areas")
        ordering = ("sort_order", "slug")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:securityarea", args=[self.pk])

    def delete(self, *args, **kwargs):
        if self.object_types.exists():
            raise ValidationError(
                _("This area still has object types. Remove them first.")
            )
        if self.object_groups.exists():
            raise ValidationError(
                _("This area still has object groups. Remove them first.")
            )
        super().delete(*args, **kwargs)


@register_search
class SecurityAreaIndex(SearchIndex):
    model = SecurityArea
    fields = (
        ("slug", 100),
        ("name", 200),
    )
