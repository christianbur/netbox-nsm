import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn

from netbox_nsm.models import ObjectGroup

__all__ = ("ObjectGroupTable",)


class ObjectGroupTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name=_("Name"))
    area = tables.Column(verbose_name=_("Area"))
    member_count = tables.Column(verbose_name=_("Members"), orderable=False)
    tags = TagColumn(url_name="plugins:netbox_nsm:objectgroup_list")

    class Meta(NetBoxTable.Meta):
        model = ObjectGroup
        fields = ("id", "name", "area", "member_count", "description", "tags")
        default_columns = ("name", "area", "member_count", "description")

    def render_member_count(self, record):
        return record.members.count() + record.sub_groups.count()

    def value_member_count(self, record):
        return record.members.count() + record.sub_groups.count()
