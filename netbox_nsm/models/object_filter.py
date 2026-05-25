from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel
from netbox.search import SearchIndex, register_search

from netbox_nsm.choices import FamilyChoices

__all__ = ("ObjectFilter", "ObjectFilterIndex")


class ObjectFilter(PrimaryModel):
    name = models.CharField(max_length=200, unique=True)
    family = models.CharField(
        max_length=20,
        choices=FamilyChoices,
        default=FamilyChoices.INET,
        verbose_name=_("Address Family"),
    )
    rules = models.JSONField(
        blank=True,
        default=list,
        verbose_name=_("Rules"),
        help_text=_(
            'List of filter rules. Each rule: {"match": "...", "value": "...", "action": "..."}'
        ),
    )

    class Meta:
        verbose_name = _("Filter Object")
        verbose_name_plural = _("Filter Objects")
        ordering = ("family", "name")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:objectfilter", args=[self.pk])


@register_search
class ObjectFilterIndex(SearchIndex):
    model = ObjectFilter
    fields = (("name", 100), ("description", 500))
