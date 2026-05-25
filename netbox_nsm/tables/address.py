import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn, ActionsColumn

from netbox_nsm.models import Address

__all__ = (
    "AddressTable",
)


class AddressTable(NetBoxTable):
    name = tables.LinkColumn()
    object_type = tables.Column(
        accessor=tables.A("assigned_object_type"),
        verbose_name=_("Type"),
    )
    assigned_object = tables.Column(
        linkify=True,
        orderable=False,
        verbose_name=_("Assigned Object"),
    )
    tags = TagColumn(url_name="plugins:netbox_nsm:address_list")

    def render_object_type(self, value):
        if not value:
            return "-"
        return value.name

    class Meta(NetBoxTable.Meta):
        model = Address
        fields = (
            "id",
            "name",
            "description",
            "object_type",
            "assigned_object",
            "dns_name",
            "tags",
        )
        default_columns = (
            "name",
            "description",
            "object_type",
            "assigned_object",
            "dns_name",
        )


