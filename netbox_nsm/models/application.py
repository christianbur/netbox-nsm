from django.urls import reverse
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from netbox.models import PrimaryModel, NetBoxModel
from netbox.models.features import ContactsMixin
from netbox.search import SearchIndex, register_search

from netbox_nsm.fields import ChoiceArrayField
from netbox_nsm.choices import ProtocolChoices
from netbox_nsm.mixins import PortsMixin

__all__ = ("Application", "ApplicationIndex")


class Application(ContactsMixin, PortsMixin, PrimaryModel):
    name = models.CharField(max_length=255)
    identifier = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    category = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    subcategory = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    application_items = models.ManyToManyField(
        to="netbox_nsm.ApplicationItem",
        blank=True,
        related_name="%(class)s_application_items",
    )
    standard_ports_text = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=_("Optional standard ports as text, e.g. tcp/22"),
    )
    technology = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    reference = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    protocol = ChoiceArrayField(
        base_field=models.CharField(
            choices=ProtocolChoices,
            blank=True,
        ),
        null=True,
        blank=True,
        default=list,
        verbose_name=_("Protocols"),
        size=5,
    )
    tenant = models.ForeignKey(
        to="tenancy.Tenant",
        on_delete=models.SET_NULL,
        related_name="%(class)s_related",
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name_plural = _("Applications")
        ordering = [
            "name",
        ]
        unique_together = [
            "name",
            "identifier",
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:application", args=[self.pk])

    @property
    def protocol_list(self):
        return ", ".join(self.protocol) if self.protocol else ""

    @property
    def standard_ports_display(self):
        linked_services = ", ".join(self.application_items.values_list("name", flat=True))
        if linked_services and self.standard_ports_text:
            return f"{linked_services}; {self.standard_ports_text}"
        return linked_services or self.standard_ports_text or ""


@register_search
class ApplicationIndex(SearchIndex):
    model = Application
    fields = (
        ("name", 100),
        ("identifier", 300),
        ("category", 300),
        ("subcategory", 300),
        ("application_items", 300),
        ("standard_ports_text", 300),
        ("technology", 300),
        ("reference", 300),
        ("protocol", 500),
        ("description", 500),
    )


