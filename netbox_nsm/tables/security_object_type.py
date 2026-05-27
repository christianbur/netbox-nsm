import django_tables2 as tables

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn

from netbox_nsm.models import SecurityObjectType

__all__ = ("SecurityObjectTypeTable",)


class SecurityObjectTypeTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name="Type")
    tags = TagColumn(url_name="plugins:netbox_nsm:object_custom_root")

    class Meta(NetBoxTable.Meta):
        model = SecurityObjectType
        fields = ("id", "name", "area", "description", "tags")
        default_columns = ("name", "area", "description")
