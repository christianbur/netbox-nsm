import django_tables2 as tables
from django.urls import reverse, NoReverseMatch
from django.utils.html import format_html, mark_safe
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable

from netbox_nsm.models import TypeConfig

__all__ = ("TypeConfigTable",)

_ACTIONS_TEMPLATE = """
<a href="{% url 'plugins:netbox_nsm:typeconfig_edit' record.pk %}"
   class="btn btn-sm btn-warning" title="Edit">
  <i class="mdi mdi-pencil"></i>
</a>
<a href="{% url 'plugins:netbox_nsm:typeconfig_delete' record.pk %}"
   class="btn btn-sm btn-danger" title="Delete">
  <i class="mdi mdi-trash-can-outline"></i>
</a>
"""


_MATCHING_CLASS_BADGE = {
    "address": ("bg-info", "text-white"),
    "zone": ("bg-primary", "text-white"),
    "label-scope": ("bg-primary", "text-white"),
    "label": ("bg-success", "text-white"),
    "service": ("bg-warning", "text-white"),
    "action": ("bg-danger", "text-white"),
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
    allowed_placements = tables.Column(
        verbose_name=_("Allowed Placements"), orderable=False
    )
    inherit_links = tables.Column(verbose_name=_("Inheritance"), orderable=True)
    inherit_stop_on_own = tables.Column(
        verbose_name=_("Stop on own link"), orderable=True
    )
    panel_linkable = tables.Column(
        verbose_name=_("Panel"), orderable=True
    )
    actions = tables.TemplateColumn(
        template_code=_ACTIONS_TEMPLATE,
        verbose_name="",
        orderable=False,
    )

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

    def render_allowed_placements(self, value):
        if not value:
            return mark_safe('<span class="text-muted">' + str(_("all")) + '</span>')
        return ", ".join(value)

    def render_inherit_links(self, value):
        if value:
            return format_html(
                '<span class="badge bg-success text-white"><i class="mdi mdi-arrow-up-circle-outline"></i> {}</span>',
                _("On"),
            )
        return mark_safe('<span class="text-muted">—</span>')

    def render_inherit_stop_on_own(self, value):
        if value:
            return format_html(
                '<span class="badge bg-warning text-white">{}</span>',
                _("Stop on own link"),
            )
        return mark_safe('<span class="text-muted">—</span>')

    def render_panel_linkable(self, value):
        if value:
            return format_html(
                '<span class="badge bg-primary text-white"><i class="mdi mdi-link-variant"></i> {}</span>',
                _("Yes"),
            )
        return mark_safe('<span class="text-muted">—</span>')

    class Meta(NetBoxTable.Meta):
        model = TypeConfig
        fields = (
            "name",
            "content_type",
            "matching_class",
            "display_template",
            "allowed_placements",
            "inherit_links",
            "inherit_stop_on_own",
            "panel_linkable",
            "actions",
        )
        default_columns = (
            "name",
            "content_type",
            "matching_class",
            "display_template",
            "allowed_placements",
            "inherit_links",
            "inherit_stop_on_own",
            "panel_linkable",
            "actions",
        )
