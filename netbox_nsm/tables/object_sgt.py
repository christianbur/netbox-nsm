import django_tables2 as tables
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import ActionsColumn, TagColumn

from netbox_nsm.models import ObjectSGT, ObjectSGTAssignment
from netbox_nsm.tables.mixins import AssignedObjectParentMixin

__all__ = ("ObjectSGTTable", "ObjectSGTAssignmentTable")


class ObjectSGTTable(NetBoxTable):
    name = tables.LinkColumn()
    tag = tables.Column(verbose_name="ID")
    tags = TagColumn(url_name="plugins:netbox_nsm:objectsgt_list")

    def render_color(self, value):
        return format_html(
            '<span style="display:inline-block;width:12px;height:12px;border:1px solid #666;background:{};margin-right:6px;vertical-align:middle"></span><code>{}</code>',
            value,
            value,
        )

    class Meta(NetBoxTable.Meta):
        model = ObjectSGT
        fields = ("id", "name", "tag", "color", "description", "tags")
        default_columns = ("name", "tag", "color", "description")


class ObjectSGTAssignmentTable(AssignedObjectParentMixin, NetBoxTable):
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
    sgt = tables.Column(verbose_name=_("SGT"), linkify=True)
    sgt_tag = tables.Column(
        accessor=tables.A("sgt__tag"),
        verbose_name=_("Tag (ID)"),
        orderable=False,
    )
    sgt_color = tables.Column(
        accessor=tables.A("sgt__color"),
        verbose_name=_("Color"),
        orderable=False,
    )
    sgt_description = tables.Column(
        accessor=tables.A("sgt__description"),
        verbose_name=_("Description"),
        orderable=False,
    )
    actions = ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = ObjectSGTAssignment
        fields = ("id", "assigned_object_parent", "assigned_object", "sgt", "sgt_tag", "sgt_color", "sgt_description")
        default_columns = ("assigned_object_parent", "assigned_object", "sgt", "sgt_tag", "sgt_color")
