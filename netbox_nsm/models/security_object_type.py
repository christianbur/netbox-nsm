from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel
from netbox.search import SearchIndex, register_search

__all__ = ("SecurityObjectType", "SecurityObjectTypeIndex")


class SecurityObjectType(PrimaryModel):
    name = models.CharField(max_length=100, unique=True)
    area = models.ForeignKey(
        "netbox_nsm.SecurityArea",
        on_delete=models.PROTECT,
        related_name="object_types",
        verbose_name=_("Area"),
    )
    field_definitions = models.JSONField(
        blank=True,
        default=list,
        help_text=_('List of field definitions: [{"name": "slug", "label": "Label"}, ...]'),
    )
    display_template = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text=_(
            'Display template for objects of this type. '
            'Use {name} and field data keys, e.g. "{name} ({port}/{protocol})". '
            'If empty, the object name is used.'
        ),
    )

    class Meta:
        verbose_name = _("Custom Type")
        verbose_name_plural = _("Custom Types")
        ordering = ("area", "name")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:securityobjecttype", args=[self.pk])


@register_search
class SecurityObjectTypeIndex(SearchIndex):
    model = SecurityObjectType
    fields = (
        ("name", 200),
        ("description", 500),
    )


# SecurityObject is defined in security_object.py
