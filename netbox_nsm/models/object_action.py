from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel
from netbox.search import SearchIndex, register_search

__all__ = ("ObjectAction", "ObjectActionIndex")


class ObjectAction(PrimaryModel):
    name = models.CharField(max_length=100, unique=True)
    action = models.CharField(max_length=100, default="permit")

    class Meta:
        verbose_name = _("Objekt (action)")
        verbose_name_plural = _("Objekte (action)")
        ordering = ("name",)

    def __str__(self):
        return f"{self.name} ({self.action})"

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:objectaction", args=[self.pk])


@register_search
class ObjectActionIndex(SearchIndex):
    model = ObjectAction
    fields = (
        ("name", 200),
        ("action", 100),
        ("description", 500),
    )
