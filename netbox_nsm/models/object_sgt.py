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

__all__ = ("ObjectSGT", "ObjectSGTIndex", "ObjectSGTAssignment")


class ObjectSGT(PrimaryModel):
    name = models.CharField(max_length=100)
    tag = models.PositiveIntegerField(blank=True, null=True)
    color = models.CharField(max_length=20, default="blue")

    class Meta:
        verbose_name = _("SGT")
        verbose_name_plural = _("SGTs")
        ordering = ("name",)
        unique_together = (("name", "tag"),)

    def __str__(self):
        if self.tag is None:
            return self.name
        return f"{self.name} ({self.tag})"

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:objectsgt", args=[self.pk])


@register_search
class ObjectSGTIndex(SearchIndex):
    model = ObjectSGT
    fields = (
        ("name", 200),
        ("description", 500),
    )


class ObjectSGTAssignment(NetBoxModel):
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
    sgt = models.ForeignKey(
        to="netbox_nsm.ObjectSGT",
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    clone_fields = ("assigned_object_type", "assigned_object_id")
    prerequisite_models = ("netbox_nsm.ObjectSGT",)

    class Meta:
        verbose_name = _("SGT Assignment")
        verbose_name_plural = _("SGT Assignments")
        indexes = (models.Index(fields=("assigned_object_type", "assigned_object_id")),)
        constraints = (
            UniqueConstraint(
                fields=("assigned_object_type", "assigned_object_id", "sgt"),
                name="netbox_nsm_objectsgtassignment_unique",
            ),
        )
        ordering = ("sgt", "assigned_object_id")

    def __str__(self):
        return str(self.sgt)

    def get_absolute_url(self):
        if self.assigned_object:
            return self.assigned_object.get_absolute_url()
        return None


GenericRelation(
    to=ObjectSGTAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="device",
).contribute_to_class(Device, "sgts")

GenericRelation(
    to=ObjectSGTAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="virtualdevicecontext",
).contribute_to_class(VirtualDeviceContext, "sgts")

GenericRelation(
    to=ObjectSGTAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="virtualmachine",
).contribute_to_class(VirtualMachine, "sgts")
