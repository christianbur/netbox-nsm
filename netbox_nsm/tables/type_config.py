import django_tables2 as tables
from django.urls import reverse, NoReverseMatch
from django.utils.html import format_html, mark_safe
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import ActionsColumn

from netbox_nsm.models import TypeConfig

__all__ = ("TypeConfigTable",)

_MATCHING_CLASS_BADGE = {
    "address": ("bg-info", "text-white"),
    "zone": ("bg-primary", "text-white"),
    "label-scope": ("bg-primary", "text-white"),
    "label": ("bg-success", "text-white"),
    "service": ("bg-warning", "text-white"),
    "action": ("bg-danger", "text-white"),
    "info": ("bg-light", "text-dark border"),
    "user": ("bg-dark", "text-white"),
    "application": ("bg-secondary", "text-white"),
    "group": ("bg-secondary", "text-white"),
    "trust": ("bg-secondary", "text-white"),
    "other": ("bg-secondary", "text-white"),
}


class TypeConfigTable(NetBoxTable):
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
    matching_class = tables.Column(verbose_name=_("Matching Class"))
    display_template = tables.Column(verbose_name=_("Display Template"))
    panel_linkable_types = tables.Column(
        verbose_name=_("Panel"),
        orderable=False,
        accessor="panel_linkable_types",
    )
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
        # Try to find the object list URL
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

    def render_matching_class(self, value):
        if not value:
            return "—"
        bg, fg = _MATCHING_CLASS_BADGE.get(value, ("bg-secondary", "text-white"))
        label = value.replace("_", " ").capitalize()
        return format_html('<span class="badge {} {}">{}</span>', bg, fg, label)

    def render_panel_linkable_types(self, record):
        if record.is_panel_linkable_disabled():
            return mark_safe('<span class="text-muted">—</span>')
        labels = record.panel_linkable_type_labels()
        if not labels:
            return format_html(
                '<span class="badge bg-primary-subtle text-primary-emphasis'
                ' border border-primary-subtle">{}</span>',
                _("All types"),
            )
        return ", ".join(labels)

    class Meta(NetBoxTable.Meta):
        model = TypeConfig
        fields = (
            "name",
            "content_type",
            "matching_class",
            "display_template",
            "panel_linkable_types",
            "actions",
        )
        default_columns = (
            "name",
            "content_type",
            "matching_class",
            "display_template",
            "panel_linkable_types",
            "actions",
        )
