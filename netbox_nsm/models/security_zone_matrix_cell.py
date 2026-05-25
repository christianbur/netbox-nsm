from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from netbox.models import NetBoxModel

__all__ = ("SecurityZoneMatrixCell",)


class SecurityZoneMatrixCell(NetBoxModel):
    matrix = models.ForeignKey(
        to="netbox_nsm.SecurityZoneMatrix",
        related_name="cells",
        on_delete=models.CASCADE,
    )
    source_zone = models.ForeignKey(
        to="netbox_nsm.SecurityZone",
        related_name="matrix_source_cells",
        on_delete=models.CASCADE,
    )
    destination_zone = models.ForeignKey(
        to="netbox_nsm.SecurityZone",
        related_name="matrix_destination_cells",
        on_delete=models.CASCADE,
    )
    policy = models.ForeignKey(
        to="netbox_nsm.SecurityZoneMatrixPolicy",
        related_name="cells",
        on_delete=models.CASCADE,
    )

    class Meta:
        verbose_name = _("Security Zone Matrix Cell").strip()
        verbose_name_plural = _("Security Zone Matrix Cells")
        unique_together = (("matrix", "source_zone", "destination_zone"),)
        ordering = ("matrix", "source_zone", "destination_zone")

    def __str__(self):
        return f"{self.matrix}: {self.source_zone} -> {self.destination_zone}: {self.policy}"

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:securityzonematrixcell", args=[self.pk])
