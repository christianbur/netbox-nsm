from django.urls import reverse
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from netbox.models import PrimaryModel, NetBoxModel
from netbox.models.features import ContactsMixin
from netbox.search import SearchIndex, register_search

from netbox_nsm.models import SecurityZone

__all__ = ("AddressSet", "AddressSetIndex")


class AddressSet(ContactsMixin, PrimaryModel):
    """ """

    name = models.CharField(max_length=200)
    identifier = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    addresses = models.ManyToManyField(
        to="netbox_nsm.Address",
        related_name="%(class)s_addresses",
    )
    address_sets = models.ManyToManyField(
        to="netbox_nsm.AddressSet",
        related_name="%(class)s_address_sets",
    )
    tenant = models.ForeignKey(
        to="tenancy.Tenant",
        on_delete=models.SET_NULL,
        related_name="%(class)s_related",
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name_plural = _("Address Sets")
        ordering = ("name",)
        unique_together = [
            "name",
            "identifier",
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:addressset", args=[self.pk])


@register_search
class AddressSetIndex(SearchIndex):
    model = AddressSet
    fields = (
        ("name", 100),
        ("identifier", 300),
        ("addresses", 300),
        ("address_sets", 300),
        ("description", 500),
    )


