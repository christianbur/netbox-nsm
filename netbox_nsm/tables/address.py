import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn, ActionsColumn

from netbox_nsm.models import Address, AddressAssignment

__all__ = (
    "AddressTable",
    "AddressAssignmentTable",
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


class AddressAssignmentTable(NetBoxTable):
    assigned_object_parent = tables.Column(
        accessor=tables.A("assigned_object__device"),
        linkify=True,
        orderable=False,
        verbose_name=_("Parent"),
    )
    assigned_object = tables.Column(
        linkify=True,
        orderable=False,
        verbose_name=_("Assigned Object"),
    )
    address = tables.Column(verbose_name=_("Address"), linkify=True)
    address_value = tables.Column(
        accessor=tables.A("address__assigned_object"),
        verbose_name=_("IP / Prefix"),
        linkify=True,
        orderable=False,
    )
    address_dns = tables.Column(
        accessor=tables.A("address__dns_name"),
        verbose_name=_("DNS Name"),
        orderable=False,
    )
    address_description = tables.Column(
        accessor=tables.A("address__description"),
        verbose_name=_("Description"),
        orderable=False,
    )
    actions = ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = AddressAssignment
        fields = ("id", "address", "address_value", "address_dns", "address_description", "assigned_object", "assigned_object_parent")
        default_columns = ("address", "address_value", "address_dns", "address_description")
