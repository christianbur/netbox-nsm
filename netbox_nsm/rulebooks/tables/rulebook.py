import django_tables2 as tables
from django.urls import reverse
from django.utils.html import conditional_escape, format_html, mark_safe
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox_nsm.rulebooks.list_row_actions import render_rulebook_list_row_actions_html
from netbox_nsm.rulebooks.permissions import RulebookListProxy
from netbox_nsm.objects.object_link_service import iter_enforcement_point_links_for_slug
from netbox_nsm.rulebooks.status import rulebook_status_badge_html
from netbox_nsm.rulebooks.virtual_cot import is_virtual_cot_rulebook

__all__ = (
    "AssignedObjectsColumn",
    "RulebookActionsColumn",
    "RulebookTable",
)

ASSIGNED_OBJECTS_MAX_VISIBLE = 2


class AssignedObjectsColumn(tables.Column):
    """Renders rulebook assignment targets from ``nsm_object_link`` COT rows."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("orderable", False)
        kwargs.setdefault("verbose_name", _("Target of enforcement targets"))
        super().__init__(*args, **kwargs)

    def _assignment_badge(self, url, name, *, hidden=False):
        style = ' style="display:none;"' if hidden else ""
        hidden_class = " nsm-assigned-hidden" if hidden else ""
        return (
            f'<a href="{conditional_escape(url)}"'
            f' class="badge text-bg-secondary text-decoration-none me-1{hidden_class}"{style}>'
            f'<i class="mdi mdi-server me-1"></i>{conditional_escape(name)}</a>'
        )

    def _items_for_record(self, record):
        if not is_virtual_cot_rulebook(record):
            return []

        items = []
        for link in iter_enforcement_point_links_for_slug(record.slug):
            obj = link.netbox_object
            if obj is None or link.policy_object is not None:
                continue
            from dcim.models import Device, VirtualDeviceContext
            from virtualization.models import VirtualMachine

            if not isinstance(obj, (Device, VirtualMachine, VirtualDeviceContext)):
                continue
            url = getattr(obj, "get_absolute_url", lambda: "#")()
            items.append((url, str(obj)))
        return items

    def render(self, value, record):
        items = self._items_for_record(record)

        if not items:
            return mark_safe('<span class="text-muted">—</span>')

        max_visible = ASSIGNED_OBJECTS_MAX_VISIBLE
        shown = items[:max_visible]
        hidden = items[max_visible:]

        parts = [self._assignment_badge(url, name) for url, name in shown]
        for url, name in hidden:
            parts.append(self._assignment_badge(url, name, hidden=True))

        if hidden:
            parts.append(
                f'<button type="button" class="badge text-bg-secondary border-0 nsm-assigned-more me-1"'
                f' style="cursor:pointer;"'
                f" onclick=\"var w=this.closest('.nsm-assigned-wrap');"
                f"w.querySelectorAll('.nsm-assigned-hidden').forEach(function(e){{e.style.display='';}});"
                f'this.remove();">+{len(hidden)}</button>'
            )

        return mark_safe(
            f'<span class="nsm-assigned-wrap d-inline-flex flex-wrap align-items-center">'
            f'{"".join(parts)}</span>'
        )


class RulebookNameColumn(tables.Column):
    def render(self, value, record):
        from netbox_nsm.rulebooks.hierarchy import render_hierarchy_marker, rulebook_list_depth

        depth = rulebook_list_depth(record)
        marker = render_hierarchy_marker(depth)
        url = record.get_absolute_url()
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
    assigned_objects = AssignedObjectsColumn(accessor="slug")
    actions = RulebookActionsColumn()

    class Meta(NetBoxTable.Meta):
        model = RulebookListProxy
        fields = (
            "name",
            "status",
            "rule_count",
            "assigned_objects",
            "description",
            "actions",
        )
        default_columns = (
            "name",
            "status",
            "rule_count",
            "assigned_objects",
            "description",
            "actions",
        )
