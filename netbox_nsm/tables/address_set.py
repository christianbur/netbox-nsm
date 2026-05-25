import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn, ActionsColumn, ManyToManyColumn
from tenancy.tables import TenancyColumnsMixin

from netbox_nsm.models import AddressSet

__all__ = (
    "AddressSetTable",
)


class AddressSetTable(TenancyColumnsMixin, NetBoxTable):
    name = tables.LinkColumn()
    addresses = ManyToManyColumn(
        linkify_item=True,
        orderable=False,
        linkify=True,
        verbose_name=_("Addresses"),
    )
    address_sets = ManyToManyColumn(
        linkify_item=True,
        orderable=False,
        linkify=True,
        verbose_name=_("Address Sets"),
    )
    tags = TagColumn(url_name="plugins:netbox_nsm:addressset_list")

    class Meta(NetBoxTable.Meta):
        model = AddressSet
        fields = (
            "id",
            "name",
            "identifier",
            "description",
            "addresses",
            "address_sets",
            "tenant",
            "tags",
        )
        default_columns = (
            "name",
            "identifier",
            "description",
            "addresses",
            "address_sets",
            "tenant",
        )


