import django_tables2 as tables
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn

from netbox_nsm.models import ObjectGroup
from netbox_nsm.panel_sections import get_panel_sections

__all__ = ("ObjectGroupTable",)

_SLUG_LABELS = {s["slug"]: str(s["name"]) for s in get_panel_sections()}


class ObjectGroupTable(NetBoxTable):
    name = tables.Column(linkify=True)
    field_slugs = tables.Column(verbose_name=_("Field slugs"), orderable=False)
    sub_groups = tables.Column(verbose_name=_("Sub-Groups"), orderable=False, accessor=tables.A("pk"))
    tags = TagColumn(url_name="plugins:netbox_nsm:objectgroup_list")

    class Meta(NetBoxTable.Meta):
        model = ObjectGroup
        fields = (
            "pk",
            "id",
            "name",
            "field_slugs",
            "color",
            "sub_groups",
            "description",
            "comments",
            "tags",
        )
        default_columns = (
            "name",
            "field_slugs",
            "color",
            "sub_groups",
            "description",
            "tags",
        )

    def render_field_slugs(self, record):
        slugs = record.field_slugs or []
        if not slugs:
            return "—"
        return ", ".join(_SLUG_LABELS.get(s, s) for s in slugs)

    def render_sub_groups(self, record):
        groups = list(record.sub_groups.all())
        if not groups:
            return mark_safe("—")
        return format_html_join(
            ", ",
            '<a href="{}">{}</a>',
            ((g.get_absolute_url(), g.name) for g in sorted(groups, key=lambda g: g.name)),
        )
