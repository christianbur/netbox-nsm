import django_tables2 as tables

from netbox.tables import NetBoxTable
from netbox.tables.columns import ChoiceFieldColumn, TagColumn

from netbox_nsm.models import ObjectInterface

__all__ = ("ObjectInterfaceTable",)


class ObjectInterfaceTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name="Name")
    direction = ChoiceFieldColumn(verbose_name="Direction")
    device = tables.Column(verbose_name="Device", linkify=True)
    interface = tables.Column(verbose_name="Interface", linkify=True)
    tags = TagColumn(url_name="plugins:netbox_nsm:objectinterface_list")

    class Meta(NetBoxTable.Meta):
        model = ObjectInterface
        fields = ("id", "name", "direction", "device", "interface", "description", "tags")
        default_columns = ("name", "direction", "device", "interface", "description")
