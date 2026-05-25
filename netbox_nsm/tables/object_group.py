import django_tables2 as tables
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import TagColumn

from netbox_nsm.models import ObjectGroup

__all__ = ("ObjectGroupTable",)


class ObjectGroupTable(NetBoxTable):
    name = tables.LinkColumn(verbose_name=_("Name"))
    area = tables.Column(verbose_name=_("Area"))
    member_count = tables.Column(verbose_name=_("Members"), orderable=False, accessor=tables.A("pk"))
    parent_groups_col = tables.Column(verbose_name=_("Parent Groups"), orderable=False, accessor=tables.A("pk"))
    tags = TagColumn(url_name="plugins:netbox_nsm:objectgroup_list")

    class Meta(NetBoxTable.Meta):
        model = ObjectGroup
        fields = ("id", "name", "area", "parent_groups_col", "member_count", "description", "tags")
        default_columns = ("name", "area", "parent_groups_col", "member_count", "description")

    def render_member_count(self, record):
        parts = []
        for m in record.members.all():
            parts.append(format_html('<a href="{}">{}</a>', m.get_absolute_url(), m.name))
        for g in record.sub_groups.all():
            parts.append(format_html('<a href="{}">{}</a>', g.get_absolute_url(), g.name))
        parts.sort(key=lambda s: s.lower() if isinstance(s, str) else str(s))
        if not parts:
            return mark_safe("—")
        return format_html_join(", ", "{}", ((p,) for p in sorted(parts, key=str)))

    def render_parent_groups_col(self, record):
        parents = list(record.parent_groups.all())
        if not parents:
            return mark_safe("—")
        return format_html_join(
            ", ",
            '<a href="{}">{}</a>',
            ((g.get_absolute_url(), g.name) for g in sorted(parents, key=lambda g: g.name)),
        )

    def value_member_count(self, record):
        names = list(record.members.values_list("name", flat=True))
        names += list(record.sub_groups.values_list("name", flat=True))
        return ", ".join(sorted(names))
