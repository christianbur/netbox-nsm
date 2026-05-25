from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel
from netbox.search import SearchIndex, register_search
from utilities.choices import ChoiceSet

__all__ = ("ObjectInterface", "ObjectInterfaceIndex", "InterfaceDirectionChoices")


class InterfaceDirectionChoices(ChoiceSet):
    SOURCE = "source"
    DESTINATION = "destination"

    CHOICES = [
        (SOURCE, "Source", "blue"),
        (DESTINATION, "Destination", "green"),
    ]


class ObjectInterface(PrimaryModel):
    name = models.CharField(max_length=100, unique=True)
    direction = models.CharField(
        max_length=20,
        choices=InterfaceDirectionChoices,
        default=InterfaceDirectionChoices.SOURCE,
        verbose_name=_("Direction"),
    )
    device = models.ForeignKey(
        to="dcim.Device",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="%(class)s_device",
        verbose_name=_("Device"),
    )
    interface = models.ForeignKey(
        to="dcim.Interface",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="%(class)s_interface",
        verbose_name=_("Interface"),
    )

    class Meta:
        verbose_name = _("Interface Object")
        verbose_name_plural = _("Interface Objects")
        ordering = ("direction", "name")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:objectinterface", args=[self.pk])


@register_search
class ObjectInterfaceIndex(SearchIndex):
    model = ObjectInterface
    fields = (("name", 100), ("description", 500))
