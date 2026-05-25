import django_tables2 as tables

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn

from netbox_nsm.models import ObjectLog

__all__ = ("ObjectLogTable",)


class ObjectLogTable(NetBoxTable):
    name = tables.LinkColumn()
    enabled = tables.Column(verbose_name="Enabled")
    tags = TagColumn(url_name="plugins:netbox_nsm:objectlog_list")

    class Meta(NetBoxTable.Meta):
        model = ObjectLog
        fields = ("id", "name", "enabled", "description", "tags")
        default_columns = ("name", "enabled", "description")
