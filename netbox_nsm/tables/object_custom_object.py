import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn

from netbox_nsm.models import ObjectCustomObject, ObjectCustomObjectAssignment
from netbox_nsm.tables.mixins import AssignedObjectParentMixin

__all__ = ("ObjectCustomObjectTable", "ObjectCustomObjectAssignmentTable")


class ObjectCustomObjectTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name="Object")
    custom_type = tables.Column(verbose_name="Type", linkify=True)
    tags = TagColumn(url_name="plugins:netbox_nsm:object_custom_root")

    class Meta(NetBoxTable.Meta):
        model = ObjectCustomObject
        fields = ("id", "name", "custom_type", "description", "tags")
        default_columns = ("name", "custom_type", "description")


class ObjectCustomObjectAssignmentTable(AssignedObjectParentMixin, NetBoxTable):
    assigned_object = tables.Column(
        linkify=True,
        orderable=False,
        verbose_name=_("Assigned Object"),
    )
    custom_object = tables.Column(verbose_name=_("Custom Object"), linkify=True)
    custom_type = tables.Column(
        accessor=tables.A("custom_object__custom_type__name"),
        verbose_name=_("Type"),
        orderable=False,
    )

    class Meta(NetBoxTable.Meta):
        model = ObjectCustomObjectAssignment
        fields = ("id", "assigned_object", "custom_type", "custom_object")
        default_columns = ("assigned_object", "custom_type", "custom_object")
