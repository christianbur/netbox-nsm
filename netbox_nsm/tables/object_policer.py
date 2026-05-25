import django_tables2 as tables

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn

from netbox_nsm.models import ObjectPolicer

__all__ = ("ObjectPolicerTable",)


class ObjectPolicerTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name="Name")
    tags = TagColumn(url_name="plugins:netbox_nsm:objectpolicer_list")

    class Meta(NetBoxTable.Meta):
        model = ObjectPolicer
        fields = ("id", "name", "bandwidth_limit", "bandwidth_percent", "description", "tags")
        default_columns = ("name", "bandwidth_limit", "bandwidth_percent", "description")
