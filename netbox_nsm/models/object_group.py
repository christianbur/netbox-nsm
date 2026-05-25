from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel, PrimaryModel
from netbox.search import SearchIndex, register_search

__all__ = ("ObjectGroup", "ObjectGroupIndex")


class ObjectGroupTypeChoices(models.TextChoices):
    MIXED = "mixed", _("Mixed")
    GROUPS = "groups", _("Groups")
    ADDRESSES = "addresses", _("Addresses")
    SERVICES = "services", _("Services")
    APPLICATIONS = "applications", _("Applications")
    LABELS = "labels", _("Labels")
    ZONES = "zones", _("Zones")
    SGTS = "sgts", _("SGTs")
    USERS = "users", _("Users")


class ObjectGroup(PrimaryModel):
    GROUP_MEMBER_TYPE_CHOICES = tuple(
        (value, label)
        for value, label in ObjectGroupTypeChoices.choices
        if value not in (ObjectGroupTypeChoices.MIXED, ObjectGroupTypeChoices.GROUPS)
    )

    MEMBER_FIELD_MAP = {
        "groups": "groups",
        "addresses": "addresses",
        "services": "services",
        "applications": "applications",
        "labels": "labels",
        "zones": "zones",
        "sgts": "sgts",
        "users": "users",
    }

    name = models.CharField(max_length=100, unique=True)
    group_type = models.CharField(
        max_length=20,
        choices=ObjectGroupTypeChoices.choices,
        default=ObjectGroupTypeChoices.MIXED,
    )
    group_member_type = models.CharField(
        max_length=20,
        choices=GROUP_MEMBER_TYPE_CHOICES,
        blank=True,
        default="",
    )
    groups = models.ManyToManyField(to="self", blank=True, symmetrical=False)
    addresses = models.ManyToManyField(to="netbox_nsm.Address", blank=True)
    services = models.ManyToManyField(to="netbox_nsm.ApplicationItem", blank=True)
    applications = models.ManyToManyField(to="netbox_nsm.Application", blank=True)
    zones = models.ManyToManyField(to="netbox_nsm.SecurityZone", blank=True)

    class Meta:
        verbose_name = _("Group")
        verbose_name_plural = _("Groups")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:objectgroup", args=[self.pk])

    def get_display_member_type(self):
        return self.group_member_type or self.group_type or ObjectGroupTypeChoices.GROUPS

    def get_display_member_type_label(self):
        member_type = self.get_display_member_type()
        return ObjectGroupTypeChoices(member_type).label

    def get_member_field_name(self):
        return self.MEMBER_FIELD_MAP.get(self.get_display_member_type(), "groups")

    def get_member_objects(self):
        return getattr(self, self.get_member_field_name()).all()

    def is_zone_member_type(self):
        return self.get_display_member_type() == ObjectGroupTypeChoices.ZONES


@register_search
class ObjectGroupIndex(SearchIndex):
    model = ObjectGroup
    fields = (
        ("name", 200),
        ("description", 500),
    )

