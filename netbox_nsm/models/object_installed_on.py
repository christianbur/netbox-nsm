from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel
from netbox.search import SearchIndex, register_search

__all__ = ("ObjectInstalledOn", "ObjectInstalledOnIndex")


class ObjectInstalledOn(PrimaryModel):
    name = models.CharField(max_length=100, unique=True)
    device = models.ForeignKey(
        to="dcim.Device",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="%(class)s_device",
        verbose_name=_("Device"),
    )

    class Meta:
        verbose_name = _("Installed On Object")
        verbose_name_plural = _("Installed On Objects")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:objectinstalledon", args=[self.pk])


@register_search
class ObjectInstalledOnIndex(SearchIndex):
    model = ObjectInstalledOn
    fields = (("name", 100), ("description", 500))
