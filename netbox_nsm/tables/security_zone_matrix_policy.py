import django_tables2 as tables
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn, ActionsColumn

from netbox_nsm.models import SecurityZoneMatrixPolicy

__all__ = ("SecurityZoneMatrixPolicyTable",)


class SecurityZoneMatrixPolicyTable(NetBoxTable):
    name = tables.LinkColumn()
    action = tables.Column()
    color = tables.Column(verbose_name=_("Color"))
    tags = TagColumn(url_name="plugins:netbox_nsm:securityzonematrixpolicy_list")
    actions = ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = SecurityZoneMatrixPolicy
        fields = ("id", "name", "action", "color", "description", "tags")
        default_columns = ("name", "action", "color", "description")

    def render_action(self, value, record):
        return format_html('<span class="badge text-bg-{}">{}</span>', record.color, value)
