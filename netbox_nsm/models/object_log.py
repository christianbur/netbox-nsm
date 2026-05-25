from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel
from netbox.search import SearchIndex, register_search

__all__ = ("ObjectLog", "ObjectLogIndex")


class ObjectLog(PrimaryModel):
    name = models.CharField(max_length=100, unique=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Log")
        verbose_name_plural = _("Logs")
        ordering = ("name",)

    def __str__(self):
        state = _("Enabled") if self.enabled else _("Disabled")
        return f"{self.name} ({state})"

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:objectlog", args=[self.pk])


@register_search
class ObjectLogIndex(SearchIndex):
    model = ObjectLog
    fields = (
        ("name", 200),
        ("description", 500),
    )
