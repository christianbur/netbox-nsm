import django_tables2 as tables

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn

from netbox_nsm.models import ObjectInstalledOn

__all__ = ("ObjectInstalledOnTable",)


class ObjectInstalledOnTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name="Name")
    device = tables.Column(verbose_name="Device", linkify=True)
    tags = TagColumn(url_name="plugins:netbox_nsm:objectinstalledon_list")

    class Meta(NetBoxTable.Meta):
        model = ObjectInstalledOn
        fields = ("id", "name", "device", "description", "tags")
        default_columns = ("name", "device", "description")
