import django_tables2 as tables
from django.utils.html import format_html, mark_safe
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable

from netbox_nsm.models import NSMTypeConfig

__all__ = ("NSMTypeConfigTable",)

_ACTIONS_TEMPLATE = ""


class NSMTypeConfigTable(NetBoxTable):
    content_type = tables.Column(
        verbose_name="Objekt-Typ",
        orderable=True,
        order_by=("content_type__app_label", "content_type__model"),
    )
    areas = tables.Column(
        verbose_name="Areas",
        orderable=False,
    )
    order_id = tables.Column(verbose_name="Reihenfolge")
    display_template = tables.Column(verbose_name="Display Template")
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
        # Ersten Buchstaben groß, Rest unverändert (erhält z. B. "IP range" → "IP range")
        model_name = (
            model_name[:1].upper() + model_name[1:] if model_name else model_name
        )
        return format_html(
            '<span class="text-muted fw-semibold">{}</span>'
            ' <span class="text-muted">&rsaquo;</span> {}',
            app_name,
            model_name,
        )

    def render_areas(self, record):
        areas = list(record.areas.order_by("sort_order", "slug"))
        if not areas:
            return "—"
        links = [
            format_html('<a href="{}">{}</a>', area.get_absolute_url(), area.name)
            for area in areas
        ]
        return mark_safe(", ".join(links))

    class Meta(NetBoxTable.Meta):
        model = NSMTypeConfig
        fields = (
            "id",
            "content_type",
            "areas",
            "order_id",
            "display_template",
        )
        default_columns = (
            "content_type",
            "areas",
            "order_id",
            "display_template",
        )
        empty_text = _("No NSMTypeConfig entries found.")
