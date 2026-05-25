import django_tables2 as tables

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn

from netbox_nsm.models import NsmObjectType, NsmObjectTypeField, NsmObject

__all__ = (
    "NsmObjectTypeTable",
    "NsmObjectTypeFieldTable",
    "NsmObjectTable",
)


class NsmObjectTypeTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name="Name")
    tags = TagColumn(url_name="plugins:netbox_nsm:nsmobjecttype_list")

    class Meta(NetBoxTable.Meta):
        model = NsmObjectType
        fields = (
            "id",
            "name",
            "slug",
            "group_name",
            "description",
            "tags",
        )
        default_columns = (
            "name",
            "slug",
            "group_name",
            "description",
        )


class NsmObjectTypeFieldTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name="Field")
    nsm_object_type = tables.Column(linkify=True, verbose_name="Object Type")
    tags = TagColumn(url_name="plugins:netbox_nsm:nsmobjecttypefield_list")

    class Meta(NetBoxTable.Meta):
        model = NsmObjectTypeField
        fields = (
            "id",
            "nsm_object_type",
            "name",
            "label",
            "type",
            "required",
            "unique",
            "description",
            "tags",
        )
        default_columns = (
            "nsm_object_type",
            "name",
            "label",
            "type",
            "required",
            "unique",
            "description",
        )


class NsmObjectTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name="Object")
    nsm_object_type = tables.Column(linkify=True, verbose_name="Object Type")
    tags = TagColumn(url_name="plugins:netbox_nsm:nsmobject_list")

    class Meta(NetBoxTable.Meta):
        model = NsmObject
        fields = (
            "id",
            "nsm_object_type",
            "name",
            "source_model",
            "source_pk",
            "description",
            "tags",
        )
        default_columns = (
            "nsm_object_type",
            "name",
            "source_model",
            "source_pk",
            "description",
        )
