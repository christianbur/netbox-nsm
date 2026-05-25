import django_tables2 as tables

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn

from netbox_nsm.models import ObjectAction

__all__ = ("ObjectActionTable",)


class ObjectActionTable(NetBoxTable):
    name = tables.LinkColumn()
    action = tables.Column(verbose_name="Action")
    tags = TagColumn(url_name="plugins:netbox_nsm:objectaction_list")

    class Meta(NetBoxTable.Meta):
        model = ObjectAction
        fields = ("id", "name", "action", "description", "tags")
        default_columns = ("name", "action", "description")
