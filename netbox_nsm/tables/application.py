import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import (
    TagColumn,
    ActionsColumn,
    ManyToManyColumn,
)
from tenancy.tables import TenancyColumnsMixin

from netbox_nsm.models import Application, ApplicationAssignment

__all__ = (
    "ApplicationTable",
    "ApplicationAssignmentTable",
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


class ApplicationAssignmentTable(NetBoxTable):
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
    application = tables.Column(verbose_name=_("Application"), linkify=True)
    actions = ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = ApplicationAssignment
        fields = ("id", "application", "assigned_object", "assigned_object_parent")
        default_columns = ("application", "assigned_object", "assigned_object_parent")
