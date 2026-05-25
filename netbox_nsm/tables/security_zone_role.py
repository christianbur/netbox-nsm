import django_tables2 as tables
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn

from netbox_nsm.models import SecurityZoneRole

__all__ = ("SecurityZoneRoleTable",)


class SecurityZoneRoleTable(NetBoxTable):
    name = tables.LinkColumn()
    zone_count = tables.Column(verbose_name=_("Security Zones"), orderable=False)
    tags = TagColumn(url_name="plugins:netbox_nsm:securityzonerole_list")

    class Meta(NetBoxTable.Meta):
        model = SecurityZoneRole
        fields = (
            "id",
            "name",
            "description",
            "zone_count",
            "tags",
        )
        default_columns = (
            "name",
            "description",
            "zone_count",
        )

    def render_zone_count(self, value, record):
        url = f"{reverse('plugins:netbox_nsm:securityzone_list')}?role_id={record.pk}"
        return format_html('<a href="{}">{}</a>', url, value)
