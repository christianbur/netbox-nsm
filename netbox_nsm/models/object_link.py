from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel

__all__ = (
    "LinkPropagationChoices",
    "ObjectLink",
)


class LinkPropagationChoices(models.TextChoices):
    DIRECT = "direct", _("Direct (this object only)")
    INHERIT_IPAM = "inherit_ipam", _("Inherit to IPAM children")
    INHERIT_GROUP = "inherit_group", _("Inherit to group members")


class ObjectLink(NetBoxModel):
    """
    A bidirectional annotation that links any NetBox object (object_a)
    to an element of a TypeConfig-configured type (object_b).

    ``propagation`` controls whether the assignment also applies to children
    (IPAM containment or group membership). ``propagate_stop_on_own`` stops
    inheritance for a type when the child already has its own direct link.
    """

    object_a_type = models.ForeignKey(
        to=ContentType,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("Typ Objekt A"),
    )
    object_a_id = models.PositiveBigIntegerField(verbose_name=_("Objekt-A-ID"))
    object_a = GenericForeignKey("object_a_type", "object_a_id")

    object_b_type = models.ForeignKey(
        to=ContentType,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("Typ Objekt B"),
    )
    object_b_id = models.PositiveBigIntegerField(verbose_name=_("Objekt-B-ID"))
    object_b = GenericForeignKey("object_b_type", "object_b_id")

    propagation = models.CharField(
        max_length=20,
        choices=LinkPropagationChoices.choices,
        default=LinkPropagationChoices.DIRECT,
        verbose_name=_("Link type"),
        help_text=_(
            "Direct: only object A. Inherit: also applies to IPAM children or "
            "group members, depending on object A."
        ),
    )
    propagate_stop_on_own = models.BooleanField(
        default=False,
        verbose_name=_("Stop when child has own link"),
        help_text=_(
            "When enabled, children with their own direct link of the same NSM "
            "type no longer inherit this assignment."
        ),
    )

    comment = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Comment"),
    )

    clone_fields = (
        "object_a_type",
        "object_a_id",
        "object_b_type",
        "object_b_id",
        "propagation",
        "propagate_stop_on_own",
    )

    class Meta:
        verbose_name = _("NSM Object Link")
        verbose_name_plural = _("NSM Object Links")
        unique_together = (
            ("object_a_type", "object_a_id", "object_b_type", "object_b_id"),
        )
        indexes = [
            models.Index(fields=("object_a_type", "object_a_id")),
            models.Index(fields=("object_b_type", "object_b_id")),
            models.Index(fields=("propagation",)),
        ]

    def __str__(self):
        return f"{self.object_a} ↔ {self.object_b}"

    def to_objectchange(self, action):
        objectchange = super().to_objectchange(action)
        if self.object_a_type_id and self.object_a_id:
            objectchange.related_object_type_id = self.object_a_type_id
            objectchange.related_object_id = self.object_a_id
        return objectchange
