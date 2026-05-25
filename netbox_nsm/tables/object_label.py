import django_tables2 as tables
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import ActionsColumn, TagColumn

from netbox_nsm.models import ObjectLabel, ObjectLabelAssignment
from netbox_nsm.tables.mixins import AssignedObjectParentMixin

__all__ = ("ObjectLabelTable", "ObjectLabelAssignmentTable")


class ObjectLabelTable(NetBoxTable):
    name = tables.LinkColumn()
    label_type = tables.Column(accessor=tables.A("type_display"), verbose_name="Type")
    tags = TagColumn(url_name="plugins:netbox_nsm:objectlabel_list")

    def render_color(self, value):
        return format_html(
            '<span style="display:inline-block;width:12px;height:12px;border:1px solid #666;background:{};margin-right:6px;vertical-align:middle"></span><code>{}</code>',
            value,
            value,
        )

    class Meta(NetBoxTable.Meta):
        model = ObjectLabel
        fields = ("id", "label_type", "name", "color", "description", "tags")
        default_columns = ("label_type", "name", "color", "description")


class ObjectLabelAssignmentTable(AssignedObjectParentMixin, NetBoxTable):
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
    label = tables.Column(verbose_name=_("Label"), linkify=True)
    label_type = tables.Column(
        accessor=tables.A("label__type_display"),
        verbose_name=_("Type"),
        orderable=False,
    )
    label_color = tables.Column(
        accessor=tables.A("label__color"),
        verbose_name=_("Color"),
        orderable=False,
    )
    label_description = tables.Column(
        accessor=tables.A("label__description"),
        verbose_name=_("Description"),
        orderable=False,
    )
    actions = ActionsColumn(actions=("edit", "delete"))

    def render_label_color(self, value):
        return format_html(
            '<span style="display:inline-block;width:12px;height:12px;border:1px solid #666;background:{};margin-right:4px;vertical-align:middle"></span><code>{}</code>',
            value, value,
        )

    class Meta(NetBoxTable.Meta):
        model = ObjectLabelAssignment
        fields = ("id", "assigned_object_parent", "assigned_object", "label", "label_type", "label_color", "label_description")
        default_columns = ("assigned_object_parent", "assigned_object", "label", "label_type", "label_color")
