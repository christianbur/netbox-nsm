from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from dcim.models import Device, VirtualDeviceContext
from netbox.models import NetBoxModel
from netbox.models.features import GenericRelation
from virtualization.models import VirtualMachine

from netbox_nsm.constants import RULESET_ASSIGNMENT_MODELS

__all__ = ("CotRulebookAssignment",)


class CotRulebookAssignment(NetBoxModel):
    """Assign a deployed COT rulebook (``nsm_rb_*``) to a device, VM, or VDC."""

    assigned_object_type = models.ForeignKey(
        to=ContentType,
        limit_choices_to=RULESET_ASSIGNMENT_MODELS,
        on_delete=models.CASCADE,
    )
    assigned_object_id = models.PositiveBigIntegerField()
    assigned_object = GenericForeignKey(
        ct_field="assigned_object_type",
        fk_field="assigned_object_id",
    )
    cot_slug = models.SlugField(
        max_length=100,
        verbose_name=_("Rulebook"),
        help_text=_("Slug of the deployed COT rulebook (nsm_rb_<name>)."),
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Description"),
    )

    clone_fields = ("assigned_object_type", "assigned_object_id", "cot_slug")

    class Meta:
        indexes = (models.Index(fields=("assigned_object_type", "assigned_object_id")),)
        constraints = (
            models.UniqueConstraint(
                fields=("assigned_object_type", "assigned_object_id", "cot_slug"),
                name="%(app_label)s_%(class)s_unique_cot_assignment",
            ),
        )
        ordering = ("cot_slug", "assigned_object_id")
        verbose_name = _("Rulebook Assignment")
        verbose_name_plural = _("Rulebook Assignments")

    def __str__(self):
        return f"{self.assigned_object}: {self.cot_slug}"

    def get_absolute_url(self):
        if self.assigned_object:
            return self.assigned_object.get_absolute_url()
        return None

    @property
    def rulebook(self):
        """Virtual COT rulebook row for templates that expect ``assignment.rulebook``."""
        from netbox_nsm.rulebooks.registry import get_deployed_cot_rulebook
        from netbox_nsm.rulebooks.virtual_cot import build_virtual_cot_rulebook_row

        cot = get_deployed_cot_rulebook(self.cot_slug)
        if cot is None:
            return None
        return build_virtual_cot_rulebook_row(cot)


GenericRelation(
    to=CotRulebookAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="device",
).contribute_to_class(Device, "nsm_cot_rulebooks")

GenericRelation(
    to=CotRulebookAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="virtualdevicecontext",
).contribute_to_class(VirtualDeviceContext, "nsm_cot_rulebooks")

GenericRelation(
    to=CotRulebookAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="virtualmachine",
).contribute_to_class(VirtualMachine, "nsm_cot_rulebooks")
