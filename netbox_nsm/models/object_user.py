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

__all__ = ("ObjectUser", "ObjectUserIndex", "ObjectUserAssignment")


class ObjectUserTypeChoices(models.TextChoices):
    USER = "user", _("User")
    GROUP = "group", _("Group")


class ObjectUser(PrimaryModel):
    entry_type = models.CharField(
        max_length=20,
        choices=ObjectUserTypeChoices.choices,
        default=ObjectUserTypeChoices.USER,
    )
    name = models.CharField(max_length=100)
    dn = models.CharField(max_length=255)

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ("entry_type", "name")
        unique_together = (("entry_type", "dn"),)

    def __str__(self):
        return f"{self.get_entry_type_display()}: {self.name}"

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:objectuser", args=[self.pk])


@register_search
class ObjectUserIndex(SearchIndex):
    model = ObjectUser
    fields = (
        ("name", 200),
        ("dn", 200),
        ("description", 500),
    )


class ObjectUserAssignment(NetBoxModel):
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
    user = models.ForeignKey(
        to="netbox_nsm.ObjectUser",
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    clone_fields = ("assigned_object_type", "assigned_object_id")
    prerequisite_models = ("netbox_nsm.ObjectUser",)

    class Meta:
        verbose_name = _("User Assignment")
        verbose_name_plural = _("User Assignments")
        indexes = (models.Index(fields=("assigned_object_type", "assigned_object_id")),)
        constraints = (
            UniqueConstraint(
                fields=("assigned_object_type", "assigned_object_id", "user"),
                name="netbox_nsm_objectuserassignment_unique",
            ),
        )
        ordering = ("user", "assigned_object_id")

    def __str__(self):
        return str(self.user)

    def get_absolute_url(self):
        if self.assigned_object:
            return self.assigned_object.get_absolute_url()
        return None


GenericRelation(
    to=ObjectUserAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="device",
).contribute_to_class(Device, "nsmUsers")

GenericRelation(
    to=ObjectUserAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="virtualdevicecontext",
).contribute_to_class(VirtualDeviceContext, "nsmUsers")

GenericRelation(
    to=ObjectUserAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="virtualmachine",
).contribute_to_class(VirtualMachine, "nsmUsers")
