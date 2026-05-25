from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from netbox.models import PrimaryModel
from netbox.search import SearchIndex, register_search

from netbox_nsm.choices import ActionChoices

__all__ = (
    "SecurityZoneMatrixPolicy",
    "SecurityZoneMatrixPolicyIndex",
)


class SecurityZoneMatrixPolicy(PrimaryModel):
    name = models.CharField(max_length=100, unique=True)
    action = models.CharField(
        max_length=20,
        choices=ActionChoices,
        default=ActionChoices.PERMIT,
    )
    color = models.CharField(max_length=20, default="green")

    class Meta:
        verbose_name = _("Security Zone Matrix Policy")
        verbose_name_plural = _("Security Zone Matrix Policies")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:securityzonematrixpolicy", args=[self.pk])

    def get_action_color(self):
        return self.color


@register_search
class SecurityZoneMatrixPolicyIndex(SearchIndex):
    model = SecurityZoneMatrixPolicy
    fields = (
        ("name", 100),
        ("action", 100),
        ("description", 500),
    )
