import django_tables2 as tables
from django.urls import reverse, NoReverseMatch
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import ActionsColumn

from netbox_nsm.models import TypeConfig

__all__ = ("TypeConfigTable",)


class TypeConfigTable(NetBoxTable):
    sort_order = tables.Column(
        verbose_name=_("Sort order"),
        orderable=True,
    )
    name = tables.Column(
        verbose_name=_("Name"),
        orderable=True,
        linkify=True,
    )
    content_type = tables.Column(
        verbose_name=_("Object Type"),
        orderable=True,
        order_by=("content_type__app_label", "content_type__model"),
    )
    display_template = tables.Column(verbose_name=_("Display Template"))
    actions = ActionsColumn(actions=("edit", "delete"))

    def render_content_type(self, value):
        if not value:
            return "—"
        model_class = value.model_class()
        if model_class:
            app_name = model_class._meta.app_config.verbose_name
            model_name = str(model_class._meta.verbose_name)
        else:
            app_name = value.app_label.upper()
            model_name = value.model
        model_name = (
            model_name[:1].upper() + model_name[1:] if model_name else model_name
        )
        inner = format_html(
            '<span class="text-muted fw-semibold">{}</span>'
            ' <span class="text-muted">&rsaquo;</span> {}',
            app_name,
            model_name,
        )
        url = None
        for pattern in (
            f"{value.app_label}:{value.model}_list",
            f"plugins:{value.app_label}:{value.model}_list",
        ):
            try:
                url = reverse(pattern)
                break
            except NoReverseMatch:
                pass
        if url:
            return format_html('<a href="{}">{}</a>', url, inner)
        return inner

    class Meta(NetBoxTable.Meta):
        model = TypeConfig
        fields = (
            "name",
            "content_type",
            "sort_order",
            "display_template",
            "actions",
        )
        default_columns = (
            "name",
            "content_type",
            "sort_order",
            "display_template",
            "actions",
        )
