import django_tables2 as tables
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn, ActionsColumn

from netbox_nsm.models import SecurityZone

__all__ = (
    "SecurityZoneTable",
)


class SecurityZoneTable(NetBoxTable):
    name = tables.LinkColumn()
    color = tables.Column(verbose_name=_("Color"))
    tags = TagColumn(url_name="plugins:netbox_nsm:securityzone_list")

    def render_color(self, value):
        return format_html(
            '<span style="display:inline-block;width:12px;height:12px;border:1px solid #666;background:{};margin-right:6px;vertical-align:middle"></span><code>{}</code>',
            value,
            value,
        )

    class Meta(NetBoxTable.Meta):
        model = SecurityZone
        fields = (
            "id",
            "name",
            "description",
            "color",
            "tags",
        )
        default_columns = (
            "name",
            "description",
            "color",
        )


