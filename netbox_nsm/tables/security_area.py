import django_tables2 as tables

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn

from netbox_nsm.models import SecurityArea

__all__ = ("SecurityAreaTable",)


class SecurityAreaTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name="Name")
    slug = tables.Column(verbose_name="Slug")
    is_system = tables.BooleanColumn(verbose_name="System")
    tags = TagColumn(url_name="plugins:netbox_nsm:securityarea_list")

    class Meta(NetBoxTable.Meta):
        model = SecurityArea
        fields = ("id", "name", "slug", "is_system", "description", "tags")
        default_columns = ("name", "slug", "is_system", "description")
