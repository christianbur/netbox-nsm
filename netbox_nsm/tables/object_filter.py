import django_tables2 as tables

from netbox.tables import NetBoxTable
from netbox.tables.columns import ChoiceFieldColumn, TagColumn

from netbox_nsm.models import ObjectFilter

__all__ = ("ObjectFilterTable",)


class ObjectFilterTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name="Name")
    family = ChoiceFieldColumn(verbose_name="Family")
    tags = TagColumn(url_name="plugins:netbox_nsm:objectfilter_list")

    class Meta(NetBoxTable.Meta):
        model = ObjectFilter
        fields = ("id", "name", "family", "description", "tags")
        default_columns = ("name", "family", "description")
