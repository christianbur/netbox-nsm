import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import ActionsColumn, TagColumn

from netbox_nsm.models import SecurityObject, SecurityObjectAssignment
from netbox_nsm.tables.mixins import AssignedObjectParentMixin

__all__ = ("SecurityObjectTable", "SecurityObjectAssignmentTable")


class SecurityObjectTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name="Object")
    custom_type = tables.Column(verbose_name="Type", linkify=True)
    tags = TagColumn(url_name="plugins:netbox_nsm:object_custom_root")
    actions = ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = SecurityObject
        fields = ("pk", "id", "name", "custom_type", "description", "tags", "actions")
        default_columns = ("pk", "name", "custom_type", "description", "actions")


class SecurityObjectAssignmentTable(AssignedObjectParentMixin, NetBoxTable):
    assigned_object_type_label = tables.Column(
        accessor=tables.A("assigned_object_type"),
        verbose_name=_("Assigned Object Type"),
        orderable=False,
    )
    assigned_object = tables.Column(
        linkify=True,
        orderable=False,
        verbose_name=_("Assigned Object"),
    )
    custom_object = tables.Column(verbose_name=_("Custom Object"), linkify=True)
    custom_type = tables.Column(
        accessor=tables.A("custom_object__custom_type__name"),
        verbose_name=_("Type"),
        orderable=False,
    )
    comment = tables.Column(verbose_name=_("Comment"), orderable=False)

    def render_assigned_object_type_label(self, value):
        if value:
            model_class = value.model_class()
            if model_class:
                return model_class._meta.verbose_name.title()
        return "—"

    class Meta(NetBoxTable.Meta):
        model = SecurityObjectAssignment
        fields = ("id", "assigned_object_type_label", "assigned_object", "custom_type", "custom_object", "comment")
        default_columns = ("assigned_object_type_label", "assigned_object", "comment")
