import django_tables2 as tables

from netbox.tables import NetBoxTable
from netbox.tables.columns import ChoiceFieldColumn, TagColumn

from netbox_nsm.models import ObjectNAT

__all__ = ("ObjectNATTable",)


class ObjectNATTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name="Name")
    nat_type = ChoiceFieldColumn(verbose_name="Type")
    tags = TagColumn(url_name="plugins:netbox_nsm:objectnat_list")

    class Meta(NetBoxTable.Meta):
        model = ObjectNAT
        fields = ("id", "name", "nat_type", "source_address", "source_prefix", "destination_address", "destination_prefix", "description", "tags")
        default_columns = ("name", "nat_type", "source_address", "destination_address", "description")
