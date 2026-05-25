from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel
from netbox.search import SearchIndex, register_search

__all__ = ("ObjectPolicer", "ObjectPolicerIndex")


class ObjectPolicer(PrimaryModel):
    name = models.CharField(max_length=100, unique=True)
    bandwidth_limit = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(32000), MaxValueValidator(50000000000)],
        verbose_name=_("Bandwidth Limit (bits/s)"),
        help_text=_("Bandwidth limit in bits per second (32000 – 50000000000)"),
    )
    bandwidth_percent = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name=_("Bandwidth Percent"),
        help_text=_("Bandwidth limit as percentage (1–100)"),
    )

    class Meta:
        verbose_name = _("Policer Object")
        verbose_name_plural = _("Policer Objects")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:objectpolicer", args=[self.pk])


@register_search
class ObjectPolicerIndex(SearchIndex):
    model = ObjectPolicer
    fields = (("name", 100), ("description", 500))
