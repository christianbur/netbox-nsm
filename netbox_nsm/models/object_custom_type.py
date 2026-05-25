from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel
from netbox.search import SearchIndex, register_search

__all__ = ("ObjectCustomType", "ObjectCustomTypeIndex", "AreaChoices")


class AreaChoices(models.TextChoices):
    SRCDST = "srcdst", _("Source/Destination")
    SERVICES = "services", _("Services")
    ACTION = "action", _("Action")
    INFO = "info", _("Info")


class ObjectCustomType(PrimaryModel):
    name = models.CharField(max_length=100, unique=True)
    area = models.CharField(
        max_length=20,
        choices=AreaChoices.choices,
        default=AreaChoices.SRCDST,
    )
    icon = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text=_(
            "MDI-Icon-Name von pictogrammers.com (z.B. \"mdi-server\", \"mdi-tag\"). "
            "Immer mit \"mdi-\" Präfix angeben."
        ),
    )
    field_definitions = models.JSONField(
        blank=True,
        default=list,
        help_text=_('List of field definitions: [{"name": "slug", "label": "Label"}, ...]'),
    )

    class Meta:
        verbose_name = _("Custom Type")
        verbose_name_plural = _("Custom Types")
        ordering = ("area", "name")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:objectcustomtype", args=[self.pk])


@register_search
class ObjectCustomTypeIndex(SearchIndex):
    model = ObjectCustomType
    fields = (
        ("name", 200),
        ("description", 500),
    )


# ObjectCustomObject is defined in object_custom_object.py
