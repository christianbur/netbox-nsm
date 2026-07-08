import django_tables2 as tables
from django.utils.html import conditional_escape, format_html, mark_safe
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox_nsm.rulebooks.list_row_actions import render_rulebook_list_row_actions_html
from netbox_nsm.rulebooks.permissions import RulebookListProxy
from netbox_nsm.rulebooks.status import rulebook_status_badge_html
from netbox_nsm.rulebooks.virtual_cot import is_virtual_cot_rulebook

__all__ = (
    "RulebookActionsColumn",
    "RulebookTable",
)


class RulebookNameColumn(tables.Column):
    def render(self, value, record):
        from netbox_nsm.rulebooks.hierarchy import render_hierarchy_marker, rulebook_list_depth

        depth = rulebook_list_depth(record)
        marker = render_hierarchy_marker(depth)
        url = record.get_rules_tab_url()
        link = format_html(
            '<a href="{}" class="nsm-rb-name-link">{}</a>',
            url,
            value,
        )
        if marker:
            return format_html(
                '<span class="d-inline-flex align-items-center gap-1">{}{}</span>',
                mark_safe(marker),
                link,
            )
        return link


class RulebookStatusColumn(tables.Column):
    def render(self, value, record):
        if is_virtual_cot_rulebook(record):
            return mark_safe(
                rulebook_status_badge_html(
                    "active",
                    label=str(_("Active")),
                )
            )
        return mark_safe(rulebook_status_badge_html(record.status))


class RulebookActionsColumn(tables.Column):
    """Edit / delete split button for virtual COT rulebook rows."""

    attrs = {
        "td": {
            "class": "text-end text-nowrap noprint p-1",
        }
    }
    empty_values = ()

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("orderable", False)
        kwargs.setdefault("verbose_name", "")
        super().__init__(*args, **kwargs)

    def header(self):
        return ""

    def render(self, record, table, **kwargs):
        request = table.context.get("request")
        if not request:
            return mark_safe("")
        html = render_rulebook_list_row_actions_html(request, record)
        return mark_safe(html)


class RulebookTable(NetBoxTable):
    name = RulebookNameColumn(
        linkify=False,
        verbose_name=_("Name"),
        orderable=True,
        attrs={"td": {"class": "text-nowrap"}},
    )
    status = RulebookStatusColumn(
        verbose_name=_("Status"),
        accessor="status",
        orderable=False,
        attrs={
            "th": {"style": "width: 1%; white-space: nowrap;"},
            "td": {"style": "white-space: nowrap;"},
        },
    )
    rule_count = tables.TemplateColumn(
        template_code="""
{% load i18n %}
<div class="nsm-rule-pills">
  <a href="{% url 'plugins:netbox_nsm:cot_rulebook_rules' slug=record.slug %}"
     class="nsm-rule-pill nsm-rule-pill--counter nsm-rulebook-count-pill text-decoration-none"
     title="{% trans 'View rules' %}">
    {{ record.rule_count }}
  </a>
</div>
        """,
        verbose_name=_("Rules"),
        accessor="rule_count",
        orderable=False,
        attrs={
            "th": {"style": "width: 1%; white-space: nowrap;"},
            "td": {"style": "white-space: nowrap;"},
        },
    )
    description = tables.Column(verbose_name=_("Description"))
    actions = RulebookActionsColumn()

    class Meta(NetBoxTable.Meta):
        model = RulebookListProxy
        fields = (
            "name",
            "status",
            "rule_count",
            "description",
            "actions",
        )
        default_columns = (
            "name",
            "status",
            "rule_count",
            "description",
            "actions",
        )
