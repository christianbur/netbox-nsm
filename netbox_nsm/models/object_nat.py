from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel
from netbox.search import SearchIndex, register_search
from utilities.choices import ChoiceSet

__all__ = ("ObjectNAT", "ObjectNATIndex", "NatObjectTypeChoices")


class NatObjectTypeChoices(ChoiceSet):
    SNAT = "snat"
    DNAT = "dnat"
    MASQUERADE = "masquerade"

    CHOICES = [
        (SNAT, "Source NAT (SNAT)", "blue"),
        (DNAT, "Destination NAT (DNAT)", "green"),
        (MASQUERADE, "Masquerade", "orange"),
    ]


class ObjectNAT(PrimaryModel):
    name = models.CharField(max_length=100, unique=True)
    nat_type = models.CharField(
        max_length=20,
        choices=NatObjectTypeChoices,
        default=NatObjectTypeChoices.SNAT,
        verbose_name=_("NAT Type"),
    )
    source_address = models.ForeignKey(
        to="ipam.IPAddress",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="%(class)s_source_address",
        verbose_name=_("Source Address"),
    )
    source_prefix = models.ForeignKey(
        to="ipam.Prefix",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="%(class)s_source_prefix",
        verbose_name=_("Source Prefix"),
    )
    destination_address = models.ForeignKey(
        to="ipam.IPAddress",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="%(class)s_destination_address",
        verbose_name=_("Destination Address"),
    )
    destination_prefix = models.ForeignKey(
        to="ipam.Prefix",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="%(class)s_destination_prefix",
        verbose_name=_("Destination Prefix"),
    )

    class Meta:
        verbose_name = _("NAT Object")
        verbose_name_plural = _("NAT Objects")
        ordering = ("nat_type", "name")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:objectnat", args=[self.pk])

    def get_nat_type_color(self):
        return NatObjectTypeChoices.colors.get(self.nat_type)


@register_search
class ObjectNATIndex(SearchIndex):
    model = ObjectNAT
    fields = (("name", 100), ("description", 500))
