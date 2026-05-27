from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import UniqueConstraint
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel
from netbox_nsm.constants import OBJECT_ASSIGNMENT_MODELS

__all__ = ("SecurityObjectAssignment",)


class SecurityObjectAssignment(NetBoxModel):
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
    custom_object = models.ForeignKey(
        to="netbox_nsm.SecurityObject",
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name=_("Custom Object"),
    )
    comment = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name=_("Comment"),
    )
    clone_fields = ("assigned_object_type", "assigned_object_id")
    prerequisite_models = ("netbox_nsm.SecurityObject",)

    class Meta:
        verbose_name = _("Custom Object Assignment")
        verbose_name_plural = _("Custom Object Assignments")
        indexes = (
            models.Index(fields=("assigned_object_type", "assigned_object_id")),
        )
        constraints = (
            UniqueConstraint(
                fields=("assigned_object_type", "assigned_object_id", "custom_object"),
                name="netbox_nsm_securityobjectassignment_unique",
            ),
        )
        ordering = ("custom_object",)

    def __str__(self):
        return str(self.custom_object)

    def get_absolute_url(self):
        if self.assigned_object:
            return self.assigned_object.get_absolute_url()
        return None
