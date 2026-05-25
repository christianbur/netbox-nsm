from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from netbox.models import NetBoxModel
from dcim.models import Device, VirtualDeviceContext
from virtualization.models import VirtualMachine
from netbox.search import SearchIndex, register_search

from netbox_nsm.constants import (
    ADDRESS_ASSIGNMENT_MODELS,
    ADDRESS_LIST_ASSIGNMENT_MODELS,
)
from netbox_nsm.models import SecurityZone, Address, AddressSet

__all__ = ("AddressList", "AddressListAssignment", "AddressListIndex")


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


class AddressListAssignment(NetBoxModel):
    assigned_object_type = models.ForeignKey(
        to="contenttypes.ContentType",
        limit_choices_to=ADDRESS_ASSIGNMENT_MODELS,
        on_delete=models.CASCADE,
    )
    assigned_object_id = models.PositiveBigIntegerField()
    assigned_object = GenericForeignKey(
        ct_field="assigned_object_type", fk_field="assigned_object_id"
    )
    address_list = models.ForeignKey(
        to="netbox_nsm.AddressList", on_delete=models.CASCADE
    )

    clone_fields = ("assigned_object_type", "assigned_object_id")

    prerequisite_models = ("netbox_nsm.AddressList",)

    class Meta:
        indexes = (models.Index(fields=("assigned_object_type", "assigned_object_id")),)
        constraints = (
            models.UniqueConstraint(
                fields=("assigned_object_type", "assigned_object_id", "address_list"),
                name="%(app_label)s_%(class)s_unique_address",
            ),
        )
        ordering = ("address_list", "assigned_object_id")
        verbose_name = _("Address List Assignment")
        verbose_name_plural = _("Address List Assignments")

    def _safe_assigned_object(self):
        try:
            return self.assigned_object
        except Exception:
            return None

    def __str__(self):
        assigned_object = self._safe_assigned_object()
        if assigned_object is None:
            return str(self.address_list)
        return f"{assigned_object}: {self.address_list}"

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


GenericRelation(
    to=AddressListAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="device",
).contribute_to_class(Device, "address_lists")

GenericRelation(
    to=AddressListAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="security_zone",
).contribute_to_class(SecurityZone, "address_lists")

GenericRelation(
    to=AddressListAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="virtualdevicecontext",
).contribute_to_class(VirtualDeviceContext, "address_lists")

GenericRelation(
    to=AddressListAssignment,
    content_type_field="assigned_object_type",
    object_id_field="assigned_object_id",
    related_query_name="virtualmachine",
).contribute_to_class(VirtualMachine, "address_lists")
