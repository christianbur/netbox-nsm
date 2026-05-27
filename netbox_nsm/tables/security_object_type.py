import django_tables2 as tables

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn

from netbox_nsm.models import SecurityObjectType

__all__ = ("SecurityObjectTypeTable",)


class SecurityObjectTypeTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name="Type")
    display_template = tables.Column(verbose_name="Display Template")
    tags = TagColumn(url_name="plugins:netbox_nsm:object_custom_root")

    class Meta(NetBoxTable.Meta):
        model = SecurityObjectType
        fields = ("id", "name", "area", "display_template", "description", "tags")
        default_columns = ("name", "area", "display_template", "description")
