import django_tables2 as tables
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import ActionsColumn, ManyToManyColumn, TagColumn
from netbox_nsm.tables.mixins import AssignedObjectParentMixin

from netbox_nsm.models import ObjectGroup, ObjectGroupAssignment

__all__ = ("ObjectGroupTable", "ObjectGroupAssignmentTable")


class ObjectGroupTable(NetBoxTable):
    name = tables.LinkColumn()
    groups = ManyToManyColumn(linkify_item=True, orderable=False)
    addresses = ManyToManyColumn(linkify_item=True, orderable=False)
    services = ManyToManyColumn(linkify_item=True, orderable=False)
    applications = ManyToManyColumn(linkify_item=True, orderable=False)
    labels = ManyToManyColumn(linkify_item=True, orderable=False)
    zones = ManyToManyColumn(linkify_item=True, orderable=False)
    sgts = ManyToManyColumn(linkify_item=True, orderable=False)
    users = ManyToManyColumn(linkify_item=True, orderable=False)
    members = tables.Column(
        empty_values=(),
        orderable=False,
        attrs={"td": {"style": "white-space: pre-line;"}},
    )
    tags = TagColumn(url_name="plugins:netbox_nsm:objectgroup_list")

    def render_members(self, record):
        member_field = record.MEMBER_FIELD_MAP.get(record.group_type)
        if not member_field:
            return "-"

        members = list(getattr(record, member_field).all())
        if record.group_type != "groups":
            members.extend(record.groups.all())

        if not members:
            return "-"

        return format_html_join(
            mark_safe("<br>"),
            '<a href="{}">{}</a>',
            (
                (member.get_absolute_url(), str(member))
                for member in members
            ),
        )

    class Meta(NetBoxTable.Meta):
        model = ObjectGroup
        fields = (
            "id",
            "name",
            "group_type",
            "members",
            "groups",
            "addresses",
            "services",
            "applications",
            "labels",
            "zones",
            "sgts",
            "users",
            "description",
            "tags",
        )
        default_columns = ("name", "group_type", "members", "description")


class ObjectGroupAssignmentTable(AssignedObjectParentMixin, NetBoxTable):
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
    group = tables.Column(verbose_name=_("Group"), linkify=True)
    group_type = tables.Column(
        accessor=tables.A("group__group_type"),
        verbose_name=_("Type"),
        orderable=False,
    )
    group_description = tables.Column(
        accessor=tables.A("group__description"),
        verbose_name=_("Description"),
        orderable=False,
    )
    actions = ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = ObjectGroupAssignment
        fields = ("id", "assigned_object_parent", "assigned_object", "group", "group_type", "group_description")
        default_columns = ("assigned_object_parent", "assigned_object", "group", "group_type")
