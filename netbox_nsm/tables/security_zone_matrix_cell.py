import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import ActionsColumn

from netbox_nsm.models import SecurityZoneMatrixCell

__all__ = ("SecurityZoneMatrixCellTable",)


class SecurityZoneMatrixCellTable(NetBoxTable):
    matrix = tables.Column(linkify=True)
    source_zone = tables.Column(linkify=True)
    destination_zone = tables.Column(linkify=True)
    policy = tables.Column(linkify=True)
    actions = ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = SecurityZoneMatrixCell
        fields = (
            "id",
            "matrix",
            "source_zone",
            "destination_zone",
            "policy",
        )
        default_columns = ("matrix", "source_zone", "destination_zone", "policy")
