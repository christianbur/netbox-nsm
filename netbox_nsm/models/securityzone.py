from django.urls import reverse
from django.db import models
from django.utils.translation import gettext_lazy as _
from netbox.search import SearchIndex, register_search

from netbox.models import PrimaryModel, NetBoxModel
from netbox.models.features import ContactsMixin

__all__ = ("SecurityZone", "SecurityZoneIndex")


class SecurityZone(ContactsMixin, PrimaryModel):
    name = models.CharField(
        max_length=100,
    )
    color = models.CharField(max_length=7, default="#808080")
    identifier = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    tenant = models.ForeignKey(
        to="tenancy.Tenant",
        on_delete=models.SET_NULL,
        related_name="%(class)s_related",
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name_plural = _("Security Zones")
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
        return reverse("plugins:netbox_nsm:securityzone", args=[self.pk])

    @classmethod
    def annotated_queryset(cls):
        """Construct an efficient queryset for this model and related data."""
        return (
            cls.objects.defer("id")
            .prefetch_related("source_zone_policies", "destination_zone_policies")
            .annotate(
                source_policy_count=models.Count(
                    "source_zone_policies",
                    distinct=True,
                ),
                destination_policy_count=models.Count(
                    "destination_zone_policies",
                    distinct=True,
                ),
            )
        )


@register_search
class SecurityZoneIndex(SearchIndex):
    model = SecurityZone
    fields = (
        ("name", 100),
        ("color", 100),
        ("identifier", 300),
        ("description", 500),
    )


