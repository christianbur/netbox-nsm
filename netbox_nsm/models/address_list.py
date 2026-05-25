from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from netbox.models import NetBoxModel
from netbox.search import SearchIndex, register_search

from netbox_nsm.constants import (
    ADDRESS_LIST_ASSIGNMENT_MODELS,
)
from netbox_nsm.models import Address, AddressSet

__all__ = ("AddressList", "AddressListIndex")


class AddressList(NetBoxModel):
    name = models.CharField(max_length=200)
    assigned_object_type = models.ForeignKey(
        to="contenttypes.ContentType",
        limit_choices_to=ADDRESS_LIST_ASSIGNMENT_MODELS,
        on_delete=models.CASCADE,
        related_name="+",
        blank=True,
        null=True,
    )
    assigned_object_id = models.PositiveBigIntegerField(
        blank=True,
        null=True,
    )
    assigned_object = GenericForeignKey(
        ct_field="assigned_object_type",
        fk_field="assigned_object_id",
    )

    class Meta:
        verbose_name_plural = _("Address Lists")
        indexes = (models.Index(fields=("assigned_object_type", "assigned_object_id")),)
        ordering = ("name", "assigned_object_id")
        constraints = (
            models.UniqueConstraint(
                fields=("assigned_object_type", "assigned_object_id", "name"),
                name="%(app_label)s_%(class)s_unique_address",
            ),
        )

    def _safe_assigned_object(self):
        try:
            return self.assigned_object
        except Exception:
            return None

    def __str__(self):
        assigned_object = self._safe_assigned_object()
        if assigned_object is None:
            return self.name
        return f"{assigned_object}: {self.name}"

    def get_absolute_url(self):
        assigned_object = self._safe_assigned_object()
        if assigned_object:
            return assigned_object.get_absolute_url()
        return None


@register_search
class AddressListIndex(SearchIndex):
    model = AddressList
    fields = (("name", 100),)


GenericRelation(
    to=AddressList,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="address",
).contribute_to_class(Address, "address_lists")


GenericRelation(
    to=AddressList,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="address_set",
).contribute_to_class(AddressSet, "address_lists")


