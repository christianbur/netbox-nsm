import django_tables2 as tables

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn

from netbox_nsm.models import ObjectComment

__all__ = ("ObjectCommentTable",)


class ObjectCommentTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name="Subject")
    tags = TagColumn(url_name="plugins:netbox_nsm:objectcomment_list")

    class Meta(NetBoxTable.Meta):
        model = ObjectComment
        fields = ("id", "name", "description", "tags")
        default_columns = ("name", "description")
