import django_tables2 as tables
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn, ActionsColumn
from netbox_nsm.tables.mixins import AssignedObjectParentMixin

from netbox_nsm.models import SecurityZone, SecurityZoneAssignment

__all__ = (
    "SecurityZoneTable",
    "SecurityZoneAssignmentTable",
)


class SecurityZoneTable(NetBoxTable):
    name = tables.LinkColumn()
    color = tables.Column(verbose_name=_("Color"))
    tags = TagColumn(url_name="plugins:netbox_nsm:securityzone_list")

    def render_color(self, value):
        return format_html(
            '<span style="display:inline-block;width:12px;height:12px;border:1px solid #666;background:{};margin-right:6px;vertical-align:middle"></span><code>{}</code>',
            value,
            value,
        )

    class Meta(NetBoxTable.Meta):
        model = SecurityZone
        fields = (
            "id",
            "name",
            "description",
            "color",
            "tags",
        )
        default_columns = (
            "name",
            "description",
            "color",
        )


class SecurityZoneAssignmentTable(AssignedObjectParentMixin, NetBoxTable):
    assigned_object_parent = tables.Column(
        accessor=tables.A("assigned_object__device"),
        orderable=False,
        verbose_name=_("Parent"),
        empty_values=(),
    )
    assigned_object = tables.Column(
        linkify=True,
        orderable=False,
        verbose_name=_("Assigned Object"),
    )
    zone = tables.Column(verbose_name=_("Security Zone"), linkify=True)
    zone_color = tables.Column(
        accessor=tables.A("zone__color"),
        verbose_name=_("Color"),
        orderable=False,
    )
    zone_description = tables.Column(
        accessor=tables.A("zone__description"),
        verbose_name=_("Description"),
        orderable=False,
    )
    actions = ActionsColumn(actions=("edit", "delete"))

    def render_zone_color(self, value):
        return format_html(
            '<span style="display:inline-block;width:12px;height:12px;border:1px solid #666;background:{};margin-right:4px;vertical-align:middle"></span><code>{}</code>',
            value, value,
        )

    class Meta(NetBoxTable.Meta):
        model = SecurityZoneAssignment
        fields = ("id", "assigned_object_parent", "assigned_object", "zone", "zone_color", "zone_description")
        default_columns = ("assigned_object_parent", "assigned_object", "zone", "zone_color")
