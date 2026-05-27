import django_tables2 as tables

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn

from netbox_nsm.models import SecurityPropertyType, SecurityPropertyField, SecurityProperty

__all__ = (
    "SecurityPropertyTypeTable",
    "SecurityPropertyFieldTable",
    "SecurityPropertyTable",
)


class SecurityPropertyTypeTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name="Name")
    tags = TagColumn(url_name="plugins:netbox_nsm:securitypropertytype_list")

    class Meta(NetBoxTable.Meta):
        model = SecurityPropertyType
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


class SecurityPropertyFieldTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name="Field")
    security_property_type = tables.Column(linkify=True, verbose_name="Object Type")
    tags = TagColumn(url_name="plugins:netbox_nsm:securitypropertyfield_list")

    class Meta(NetBoxTable.Meta):
        model = SecurityPropertyField
        fields = (
            "id",
            "security_property_type",
            "name",
            "label",
            "type",
            "required",
            "unique",
            "description",
            "tags",
        )
        default_columns = (
            "security_property_type",
            "name",
            "label",
            "type",
            "required",
            "unique",
            "description",
        )


class SecurityPropertyTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name="Object")
    security_property_type = tables.Column(linkify=True, verbose_name="Object Type")
    tags = TagColumn(url_name="plugins:netbox_nsm:securityproperty_list")

    class Meta(NetBoxTable.Meta):
        model = SecurityProperty
        fields = (
            "id",
            "security_property_type",
            "name",
            "source_model",
            "source_pk",
            "description",
            "tags",
        )
        default_columns = (
            "security_property_type",
            "name",
            "source_model",
            "source_pk",
            "description",
        )
