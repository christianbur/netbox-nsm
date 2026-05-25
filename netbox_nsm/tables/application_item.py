import django_tables2 as tables

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn

from netbox_nsm.models import ApplicationItem

__all__ = ("ApplicationItemTable",)


class ApplicationItemTable(NetBoxTable):
    name = tables.LinkColumn()
    protocol = tables.Column(
        accessor=tables.A("protocol_list"),
        order_by=tables.A("protocol"),
    )
    source_ports = tables.Column(
        accessor=tables.A("source_port_list"),
        order_by=tables.A("source_ports"),
    )
    destination_ports = tables.Column(
        accessor=tables.A("destination_port_list"),
        order_by=tables.A("destination_ports"),
    )
    tags = TagColumn(url_name="plugins:netbox_nsm:applicationitem_list")

    class Meta(NetBoxTable.Meta):
        model = ApplicationItem
        fields = (
            "id",
            "name",
            "description",
            "protocol",
            "destination_ports",
            "source_ports",
            "tags",
        )
        default_columns = (
            "name",
            "description",
            "protocol",
            "destination_ports",
            "source_ports",
        )
