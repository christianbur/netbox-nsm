from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import BaseModel, PrimaryModel
from netbox.models.features import ChangeLoggingMixin
from netbox.search import SearchIndex, register_search

__all__ = (
    "ObjectGroup",
    "ObjectGroupMember",
    "ObjectGroupIndex",
)


class _NsmJunctionModel(ChangeLoggingMixin, BaseModel):
    class Meta:
        abstract = True


class ObjectGroup(PrimaryModel):
    """
    A named group that aggregates NetBox objects and/or other ObjectGroups
    and can be associated with one or more rulebook field slugs.
    """

    name = models.CharField(max_length=100, unique=True, verbose_name=_("Name"))
    field_slugs = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Field slugs"),
        help_text=_(
            "Rulebook field slugs this group applies to (e.g. source, destination)."
        ),
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
        help_text=_(
            "Optional HTML color code (e.g. #aabbcc) used for this group in the policy view."
        ),
    )

    class Meta:
        verbose_name = _("Security Object Group")
        verbose_name_plural = _("Security Object Groups")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:objectgroup", args=[self.pk])

    def serialize_object(self, exclude=None):
        data = super().serialize_object(exclude=exclude)
        if self.pk:
            data["members"] = [
                {
                    "type": str(m.content_type) if m.content_type else None,
                    "object_id": m.object_id,
                }
                for m in self.member_items.select_related("content_type").order_by(
                    "content_type__app_label", "content_type__model", "object_id"
                )
            ]
        return data


class ObjectGroupMember(_NsmJunctionModel):
    """Links any NetBox object to a ObjectGroup."""

    group = models.ForeignKey(
        ObjectGroup,
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

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:objectgroup", args=[self.group_id])


@register_search
class ObjectGroupIndex(SearchIndex):
    model = ObjectGroup
    fields = (
        ("name", 200),
        ("description", 500),
    )
