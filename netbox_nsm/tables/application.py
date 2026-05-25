import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import (
    TagColumn,
    ActionsColumn,
    ManyToManyColumn,
)
from tenancy.tables import TenancyColumnsMixin

from netbox_nsm.models import Application

__all__ = (
    "ApplicationTable",
)


class ApplicationTable(TenancyColumnsMixin, NetBoxTable):
    name = tables.LinkColumn(verbose_name=_("Application Name"))
    identifier = tables.Column(verbose_name=_("App-ID Name"))
    application_items = ManyToManyColumn(
        linkify_item=True,
        orderable=False,
        linkify=True,
        verbose_name=_("Standard Ports (Services)"),
    )
    standard_ports_text = tables.Column(verbose_name=_("Standard Ports (Text)"))
    category = tables.Column(verbose_name=_("Category"))
    subcategory = tables.Column(verbose_name=_("Subcategory"))
    technology = tables.Column(verbose_name=_("Technology"))
    reference = tables.Column(verbose_name=_("Reference"))
    tags = TagColumn(url_name="plugins:netbox_nsm:application_list")

    class Meta(NetBoxTable.Meta):
        model = Application
        fields = (
            "id",
            "name",
            "identifier",
            "category",
            "subcategory",
            "description",
            "application_items",
            "standard_ports_text",
            "technology",
            "reference",
            "tenant",
            "tags",
        )
        default_columns = (
            "name",
            "identifier",
            "category",
            "subcategory",
            "description",
            "application_items",
            "standard_ports_text",
            "technology",
            "reference",
            "tenant",
        )


