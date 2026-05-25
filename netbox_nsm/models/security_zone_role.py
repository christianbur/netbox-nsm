from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from netbox.models import PrimaryModel
from netbox.search import SearchIndex, register_search

__all__ = (
    "SecurityZoneRole",
    "SecurityZoneRoleIndex",
)


class SecurityZoneRole(PrimaryModel):
    name = models.CharField(max_length=100, unique=True)
    use_matrix = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("Security Zone Role")
        verbose_name_plural = _("Security Zone Roles")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:securityzonerole", args=[self.pk])

    @classmethod
    def annotated_queryset(cls):
        return cls.objects.annotate(zone_count=models.Count("zones", distinct=True))


@register_search
class SecurityZoneRoleIndex(SearchIndex):
    model = SecurityZoneRole
    fields = (
        ("name", 100),
        ("description", 500),
    )