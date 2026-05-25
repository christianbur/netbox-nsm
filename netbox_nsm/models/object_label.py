from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import UniqueConstraint
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from dcim.models import Device, VirtualDeviceContext
from netbox.models import NetBoxModel, PrimaryModel
from netbox.search import SearchIndex, register_search
from netbox_nsm.choices import ObjectLabelTypeChoices
from netbox_nsm.constants import OBJECT_ASSIGNMENT_MODELS
from virtualization.models import VirtualMachine

__all__ = ("ObjectLabel", "ObjectLabelIndex", "ObjectLabelAssignment")


class ObjectLabel(PrimaryModel):
    label_type = models.CharField(
        max_length=32,
        choices=ObjectLabelTypeChoices,
        default=ObjectLabelTypeChoices.OTHER,
    )
    custom_type = models.CharField(max_length=100, blank=True, default="")
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#808080")

    class Meta:
        verbose_name = _("Label")
        verbose_name_plural = _("Labels")
        ordering = ("label_type", "custom_type", "name")
        constraints = (
            models.UniqueConstraint(
                fields=("label_type", "custom_type", "name"),
                name="netbox_nsm_objectlabel_unique_label_type_custom_type_name",
            ),
        )

    @property
    def type_display(self):
        if self.label_type == ObjectLabelTypeChoices.OTHER:
            return self.custom_type or "Other"
        return self.get_label_type_display()

    @property
    def display(self):
        return f"{self.type_display}:{self.name}"

    def clean(self):
        super().clean()
        if self.label_type == ObjectLabelTypeChoices.OTHER:
            if not self.custom_type.strip():
                raise ValidationError({"custom_type": _("Custom type is required for 'Other'.")})
        else:
            self.custom_type = ""

    def __str__(self):
        return self.display

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:objectlabel", args=[self.pk])


@register_search
class ObjectLabelIndex(SearchIndex):
    model = ObjectLabel
    fields = (
        ("label_type", 100),
        ("custom_type", 100),
        ("name", 200),
        ("description", 500),
    )


class ObjectLabelAssignment(NetBoxModel):
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
    label = models.ForeignKey(
        to="netbox_nsm.ObjectLabel",
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    clone_fields = ("assigned_object_type", "assigned_object_id")
    prerequisite_models = ("netbox_nsm.ObjectLabel",)

    class Meta:
        verbose_name = _("Label Assignment")
        verbose_name_plural = _("Label Assignments")
        indexes = (models.Index(fields=("assigned_object_type", "assigned_object_id")),)
        constraints = (
            UniqueConstraint(
                fields=("assigned_object_type", "assigned_object_id", "label"),
                name="netbox_nsm_objectlabelassignment_unique",
            ),
        )
        ordering = ("label", "assigned_object_id")

    def __str__(self):
        return str(self.label)

    def get_absolute_url(self):
        if self.assigned_object:
            return self.assigned_object.get_absolute_url()
        return None


GenericRelation(
    to=ObjectLabelAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="device",
).contribute_to_class(Device, "labels")

GenericRelation(
    to=ObjectLabelAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="virtualdevicecontext",
).contribute_to_class(VirtualDeviceContext, "labels")

GenericRelation(
    to=ObjectLabelAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="virtualmachine",
).contribute_to_class(VirtualMachine, "labels")
