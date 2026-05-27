from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel
from netbox.search import SearchIndex, register_search

__all__ = ("SecurityObjectGroup", "SecurityObjectGroupIndex")


class SecurityObjectGroup(PrimaryModel):
    """
    A named group that aggregates SecurityObjects and/or other SecurityObjectGroups
    belonging to the same area (srcdst / services / action).
    """

    name = models.CharField(max_length=100, unique=True, verbose_name=_("Name"))
    area = models.ForeignKey(
        "netbox_nsm.SecurityArea",
        on_delete=models.PROTECT,
        related_name="object_groups",
        verbose_name=_("Area"),
    )
    members = models.ManyToManyField(
        "netbox_nsm.SecurityObject",
        blank=True,
        related_name="object_groups",
        verbose_name=_("Members"),
    )
    sub_groups = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=False,
        related_name="parent_groups",
        verbose_name=_("Sub-Groups"),
    )

    class Meta:
        verbose_name = _("Object Group")
        verbose_name_plural = _("Object Groups")
        ordering = ("area", "name")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:securityobjectgroup", args=[self.pk])


@register_search
class SecurityObjectGroupIndex(SearchIndex):
    model = SecurityObjectGroup
    fields = (
        ("name", 200),
        ("description", 500),
    )
