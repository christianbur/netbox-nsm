import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import ActionsColumn, TagColumn
from netbox_nsm.tables.mixins import AssignedObjectParentMixin

from netbox_nsm.models import ObjectUser, ObjectUserAssignment

__all__ = ("ObjectUserTable", "ObjectUserAssignmentTable")


class ObjectUserTable(NetBoxTable):
    name = tables.LinkColumn()
    entry_type = tables.Column(verbose_name="Type")
    dn = tables.Column(verbose_name="Distinguished Name (DN)")
    tags = TagColumn(url_name="plugins:netbox_nsm:objectuser_list")

    def render_entry_type(self, value):
        return str(value).capitalize()

    class Meta(NetBoxTable.Meta):
        model = ObjectUser
        fields = ("id", "name", "entry_type", "dn", "description", "tags")
        default_columns = ("name", "entry_type", "dn", "description")


class ObjectUserAssignmentTable(AssignedObjectParentMixin, NetBoxTable):
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
    user = tables.Column(verbose_name=_("User"), linkify=True)
    user_type = tables.Column(
        accessor=tables.A("user__entry_type"),
        verbose_name=_("Type"),
        orderable=False,
    )
    user_dn = tables.Column(
        accessor=tables.A("user__dn"),
        verbose_name=_("Distinguished Name (DN)"),
        orderable=False,
    )
    user_description = tables.Column(
        accessor=tables.A("user__description"),
        verbose_name=_("Description"),
        orderable=False,
    )
    actions = ActionsColumn(actions=("edit", "delete"))

    def render_user_type(self, value):
        return str(value).capitalize()

    class Meta(NetBoxTable.Meta):
        model = ObjectUserAssignment
        fields = ("id", "assigned_object_parent", "assigned_object", "user", "user_type", "user_dn", "user_description")
        default_columns = ("assigned_object_parent", "assigned_object", "user", "user_type")
