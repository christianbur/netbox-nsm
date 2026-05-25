from django.urls import reverse
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from netbox.models import PrimaryModel, NetBoxModel
from netbox.models.features import ContactsMixin
from netbox.search import SearchIndex, register_search

__all__ = ("ApplicationSet", "ApplicationSetIndex")


class ApplicationSet(ContactsMixin, PrimaryModel):
    """ """

    name = models.CharField(max_length=200)
    identifier = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    applications = models.ManyToManyField(
        to="netbox_nsm.Application",
        related_name="%(class)s_applications",
        blank=True,
    )
    application_sets = models.ManyToManyField(
        to="netbox_nsm.ApplicationSet",
        related_name="%(class)s_application_sets",
        blank=True,
    )
    tenant = models.ForeignKey(
        to="tenancy.Tenant",
        on_delete=models.SET_NULL,
        related_name="%(class)s_related",
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name_plural = _("Application Sets")
        ordering = ("name",)
        unique_together = [
            "name",
            "identifier",
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:applicationset", args=[self.pk])


@register_search
class ApplicationSetIndex(SearchIndex):
    model = ApplicationSet
    fields = (
        ("name", 100),
        ("identifier", 300),
        ("applications", 300),
        ("description", 500),
    )


