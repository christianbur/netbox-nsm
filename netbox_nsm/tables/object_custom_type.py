import django_tables2 as tables

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn

from netbox_nsm.models import ObjectCustomType

__all__ = ("ObjectCustomTypeTable",)


class ObjectCustomTypeTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name="Type")
    tags = TagColumn(url_name="plugins:netbox_nsm:object_custom_root")

    class Meta(NetBoxTable.Meta):
        model = ObjectCustomType
        fields = ("id", "name", "area", "description", "tags")
        default_columns = ("name", "area", "description")
