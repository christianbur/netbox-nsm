import django_tables2 as tables
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn, ActionsColumn, ManyToManyColumn
from tenancy.tables import TenancyColumnsMixin

from netbox_nsm.models import SecurityZoneMatrix

__all__ = ("SecurityZoneMatrixTable",)


class SecurityZoneMatrixTable(TenancyColumnsMixin, NetBoxTable):
    name = tables.LinkColumn()
    roles = ManyToManyColumn(linkify_item=True, orderable=False, linkify=True)
    role_count = tables.Column(verbose_name=_("Roles"), orderable=False)
    zone_count = tables.Column(verbose_name=_("Security Zones"), orderable=False)
    cell_count = tables.Column(verbose_name=_("Cells"), orderable=False)
    tags = TagColumn(url_name="plugins:netbox_nsm:securityzonematrix_list")
    actions = ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = SecurityZoneMatrix
        fields = (
            "id",
            "name",
            "roles",
            "role_count",
            "zone_count",
            "cell_count",
            "description",
            "tenant",
            "tags",
        )
        default_columns = ("name", "roles", "role_count", "zone_count", "cell_count")
