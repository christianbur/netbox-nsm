import django_tables2 as tables
from django.urls import reverse
from django.utils.html import conditional_escape, format_html, mark_safe
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import ActionsColumn
from netbox_nsm.models import CotRulebookAssignment
from netbox_nsm.rulebooks.status import rulebook_status_badge_html
from netbox_nsm.rulebooks.virtual_cot import is_virtual_cot_rulebook

__all__ = (
    "AssignedObjectsColumn",
    "CotRulebookAssignmentTable",
    "RulebookTable",
)

ASSIGNED_OBJECTS_MAX_VISIBLE = 2


class AssignedObjectsColumn(tables.Column):
    """Renders CotRulebookAssignment targets; collapses to +N when more than two."""

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
        from django.db.models import prefetch_related_objects

        if not is_virtual_cot_rulebook(record):
            return []

        assignments = list(
            CotRulebookAssignment.objects.filter(cot_slug=record.slug)
            .select_related("assigned_object_type")
            .order_by("assigned_object_type__model", "assigned_object_id")
        )
        prefetch_related_objects(assignments, "assigned_object")

        items = []
        for assignment in assignments:
            obj = assignment.assigned_object
            if obj is None:
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

    class Meta(NetBoxTable.Meta):
        # Proxy for NetBoxTable custom-field/link resolution; rows are VirtualCotRulebook.
        model = CotRulebookAssignment
        fields = ("name", "status", "rule_count", "assigned_objects", "description")
        default_columns = ("name", "status", "rule_count", "assigned_objects", "description")


class CotRulebookAssignmentTable(NetBoxTable):
    assigned_object_parent = tables.Column(
        accessor=tables.A("assigned_object__device"),
        linkify=True,
        orderable=False,
        verbose_name=_("Parent"),
    )
    assigned_object = tables.Column(
        linkify=True,
        orderable=False,
        verbose_name=_("Assigned Object"),
    )
    rulebook = tables.TemplateColumn(
        template_code="""
<a href="{{ record.rulebook.get_absolute_url }}">{{ record.rulebook.name }}</a>
        """,
        verbose_name=_("Rulebook"),
        orderable=False,
    )
    actions = ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = CotRulebookAssignment
        fields = ("id", "rulebook", "assigned_object", "assigned_object_parent")
        default_columns = ("rulebook", "assigned_object", "assigned_object_parent")
