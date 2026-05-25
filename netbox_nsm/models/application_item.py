from django.urls import reverse
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from netbox.models import PrimaryModel
from netbox.models.features import ContactsMixin
from netbox.search import SearchIndex, register_search

from netbox_nsm.fields import ChoiceArrayField
from netbox_nsm.choices import ProtocolChoices
from netbox_nsm.mixins import PortsMixin

__all__ = ("ApplicationItem", "ApplicationItemIndex")


class ApplicationItem(ContactsMixin, PortsMixin, PrimaryModel):
    name = models.CharField(max_length=255)
    index = models.PositiveIntegerField()
    protocol = ChoiceArrayField(
        base_field=models.CharField(
            choices=ProtocolChoices,
            blank=True,
        ),
        default=list,
        verbose_name=_("Protocols"),
        null=True,
        blank=True,
        size=5,
    )

    class Meta:
        verbose_name_plural = _("Application Items")
        ordering = ["index", "name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:applicationitem", args=[self.pk])

    def clean(self):
        super().clean()
        if not self.protocol:
            raise ValidationError({"protocol": _("A protocol selection is required.")})
        if len(self.protocol) != 1:
            raise ValidationError({"protocol": _("Protocol must be a single selection.")})
        if not self.destination_ports:
            raise ValidationError(
                {"destination_ports": _("Destination ports are required.")}
            )

    @classmethod
    def get_next_index(cls):
        return (cls.objects.aggregate(max_index=models.Max("index"))["max_index"] or 0) + 1

    @property
    def protocol_list(self):
        return ", ".join(self.protocol) if self.protocol else ""


@register_search
class ApplicationItemIndex(SearchIndex):
    model = ApplicationItem
    fields = (
        ("name", 100),
        ("description", 500),
    )
