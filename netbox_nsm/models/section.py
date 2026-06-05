from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel

__all__ = ("Section",)


class Section(PrimaryModel):
    """A logical grouping of CustomObjectTypes (source, destination, services, ...).

    Replaces the legacy ``SecurityArea`` once the migration to
    netbox-custom-objects is complete. Each section can reference any number
    of ``CustomObjectType`` instances, and a single CustomObjectType can
    belong to multiple sections (e.g. ``Addresses`` is used in both
    ``source`` and ``destination``).
    """

    slug = models.SlugField(
        max_length=50,
        unique=True,
        help_text=_("Unique identifier (e.g. 'source', 'destination', 'services')."),
    )
    name = models.CharField(max_length=100)
    sort_order = models.PositiveIntegerField(
        default=100,
        help_text=_("Lower comes first in lists and navigation."),
    )
    custom_object_types = models.ManyToManyField(
        to="netbox_custom_objects.CustomObjectType",
        related_name="nsm_sections",
        blank=True,
        help_text=_("CustomObjectTypes that belong to this section."),
    )

    class Meta:
        verbose_name = _("NSM Section")
        verbose_name_plural = _("NSM Sections")
        ordering = ("sort_order", "slug")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:section", args=[self.pk])
