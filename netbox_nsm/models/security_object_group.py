from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel
from netbox.search import SearchIndex, register_search

__all__ = ("SecurityObjectGroup", "SecurityObjectGroupMember", "SecurityObjectGroupIndex")


class SecurityObjectGroup(PrimaryModel):
    """
    A named group that aggregates NetBox objects and/or other SecurityObjectGroups
    and can be associated with one or more areas.
    """

    name = models.CharField(max_length=100, unique=True, verbose_name=_("Name"))
    areas = models.ManyToManyField(
        "netbox_nsm.SecurityArea",
        related_name="object_groups",
        verbose_name=_("Areas"),
        blank=True,
    )
    sub_groups = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=False,
        related_name="parent_groups",
        verbose_name=_("Sub-Groups"),
    )
    color = models.CharField(
        max_length=7,
        blank=True,
        default="",
        help_text=_('Optional HTML color code (e.g. #aabbcc) used for this group in the policy view.'),
    )

    class Meta:
        verbose_name = _("Security Object Group")
        verbose_name_plural = _("Security Object Groups")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:securityobjectgroup", args=[self.pk])


class SecurityObjectGroupMember(models.Model):
    """Links any NetBox object to a SecurityObjectGroup."""

    group = models.ForeignKey(
        SecurityObjectGroup,
        on_delete=models.CASCADE,
        related_name="member_items",
        verbose_name=_("Gruppe"),
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name=_("Objekttyp"),
    )
    object_id = models.PositiveBigIntegerField(verbose_name=_("Objekt-ID"))
    assigned_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        unique_together = (("group", "content_type", "object_id"),)
        indexes = (models.Index(fields=("content_type", "object_id")),)
        verbose_name = _("Security Object Group Member")
        verbose_name_plural = _("Security Object Group Members")
        ordering = ("group__name",)

    def __str__(self):
        return f"{self.group} / {self.content_type} / {self.object_id}"


@register_search
class SecurityObjectGroupIndex(SearchIndex):
    model = SecurityObjectGroup
    fields = (
        ("name", 200),
        ("description", 500),
    )
