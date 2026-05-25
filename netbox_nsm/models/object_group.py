from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import UniqueConstraint
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from dcim.models import Device, VirtualDeviceContext
from netbox.models import NetBoxModel, PrimaryModel
from netbox.search import SearchIndex, register_search
from netbox_nsm.constants import OBJECT_ASSIGNMENT_MODELS
from virtualization.models import VirtualMachine

__all__ = ("ObjectGroup", "ObjectGroupIndex", "ObjectGroupAssignment")


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
    labels = models.ManyToManyField(to="netbox_nsm.ObjectLabel", blank=True)
    zones = models.ManyToManyField(to="netbox_nsm.SecurityZone", blank=True)
    sgts = models.ManyToManyField(to="netbox_nsm.ObjectSGT", blank=True)
    users = models.ManyToManyField(to="netbox_nsm.ObjectUser", blank=True)

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


class ObjectGroupAssignment(NetBoxModel):
    assigned_object_type = models.ForeignKey(
        to=ContentType,
        limit_choices_to=OBJECT_ASSIGNMENT_MODELS,
        on_delete=models.CASCADE,
        related_name="+",
    )
    assigned_object_id = models.PositiveBigIntegerField(blank=True, null=True)
    assigned_object = GenericForeignKey(
        ct_field="assigned_object_type", fk_field="assigned_object_id"
    )
    group = models.ForeignKey(
        to="netbox_nsm.ObjectGroup",
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    clone_fields = ("assigned_object_type", "assigned_object_id")
    prerequisite_models = ("netbox_nsm.ObjectGroup",)

    class Meta:
        verbose_name = _("Group Assignment")
        verbose_name_plural = _("Group Assignments")
        indexes = (models.Index(fields=("assigned_object_type", "assigned_object_id")),)
        constraints = (
            UniqueConstraint(
                fields=("assigned_object_type", "assigned_object_id", "group"),
                name="netbox_nsm_objectgroupassignment_unique",
            ),
        )
        ordering = ("group", "assigned_object_id")

    def __str__(self):
        return str(self.group)

    def get_absolute_url(self):
        if self.assigned_object:
            return self.assigned_object.get_absolute_url()
        return None


GenericRelation(
    to=ObjectGroupAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="device",
).contribute_to_class(Device, "nsmGroups")

GenericRelation(
    to=ObjectGroupAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="virtualdevicecontext",
).contribute_to_class(VirtualDeviceContext, "nsmGroups")

GenericRelation(
    to=ObjectGroupAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="virtualmachine",
).contribute_to_class(VirtualMachine, "nsmGroups")
