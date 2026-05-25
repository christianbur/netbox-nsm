import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn, ActionsColumn, ManyToManyColumn
from tenancy.tables import TenancyColumnsMixin

from netbox_nsm.models import ApplicationSet

__all__ = (
    "ApplicationSetTable",
)


class ApplicationSetTable(TenancyColumnsMixin, NetBoxTable):
    name = tables.LinkColumn()
    applications = ManyToManyColumn(
        linkify_item=True,
        orderable=False,
        linkify=True,
        verbose_name=_("Applications"),
    )
    application_sets = ManyToManyColumn(
        linkify_item=True,
        orderable=False,
        linkify=True,
        verbose_name=_("Application Sets"),
    )
    tags = TagColumn(url_name="plugins:netbox_nsm:applicationset_list")

    class Meta(NetBoxTable.Meta):
        model = ApplicationSet
        fields = (
            "id",
            "name",
            "identifier",
            "description",
            "applications",
            "application_sets",
            "tenant",
            "tags",
        )
        default_columns = (
            "name",
            "identifier",
            "description",
            "applications",
            "application_sets",
            "tenant",
        )


