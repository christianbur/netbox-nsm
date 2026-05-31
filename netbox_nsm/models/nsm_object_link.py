from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel

__all__ = ("NSMObjectLink",)


class NSMObjectLink(NetBoxModel):
    """
    A bidirectional annotation that links any NetBox object (object_a)
    to an element of an NSMTypeConfig-configured type (object_b).

    Example: Subnet 10.0.0.0/8  ↔  Zone "trust"
             Host "server01"    ↔  Label "production"
    """

    # ── Object A: the source object (e.g. the page we clicked Assign on) ──
    object_a_type = models.ForeignKey(
        to=ContentType,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("Typ Objekt A"),
    )
    object_a_id = models.PositiveBigIntegerField(verbose_name=_("Objekt-A-ID"))
    object_a = GenericForeignKey("object_a_type", "object_a_id")

    # ── Object B: an element of an NSMTypeConfig type ─────────────────────
    object_b_type = models.ForeignKey(
        to=ContentType,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("Typ Objekt B"),
    )
    object_b_id = models.PositiveBigIntegerField(verbose_name=_("Objekt-B-ID"))
    object_b = GenericForeignKey("object_b_type", "object_b_id")

    comment = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Comment"),
    )

    clone_fields = ("object_a_type", "object_a_id", "object_b_type", "object_b_id")

    class Meta:
        verbose_name = _("NSM Object Link")
        verbose_name_plural = _("NSM Object Links")
        unique_together = (("object_a_type", "object_a_id", "object_b_type", "object_b_id"),)
        indexes = [
            models.Index(fields=("object_a_type", "object_a_id")),
            models.Index(fields=("object_b_type", "object_b_id")),
        ]

    def __str__(self):
        return f"{self.object_a} ↔ {self.object_b}"
