import django_tables2 as tables
from collections import OrderedDict
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from django.utils.html import conditional_escape, escape, format_html, mark_safe
from django.utils.translation import gettext_lazy as _
from urllib.parse import quote

from netbox.tables import NetBoxTable
from netbox.tables.columns import ActionsColumn, TagColumn
from utilities.permissions import get_permission_for_model
from utilities.views import get_action_url

from netbox_nsm.models import (
    Rule,
    Rulebook,
    RulebookAssignment,
    RulebookStatusChoices,
)
from netbox_nsm.rulebook_copy import COPY_SCHEMA_LABEL, rulebook_schema_copy_add_url
from netbox_nsm.rulebook_hierarchy import render_hierarchy_marker, rulebook_list_depth
from netbox_nsm.rulebook_status import rulebook_status_badge_html
from netbox_nsm.virtual_rulebook import is_virtual_all_rules_rulebook

__all__ = (
    "RulebookTable",
    "RulebookActionsColumn",
    "RuleTable",
    "RulebookAssignmentTable",
)


# ── helper functions for rule-stack rendering ────────────────────────────────

MAX_PILLS = 3
ASSIGNED_OBJECTS_MAX_VISIBLE = 2


def _card(label, items, max_pills=MAX_PILLS):
    """
    items: list of dicts with keys 'url', 'name', optional 'style', optional 'excluded'.
    Returns an nsm-rule-card HTML string.
    First max_pills are shown; the rest collapse to a hoverable +N badge.
    """
    shown = items[:max_pills]
    hidden = items[max_pills:]

    pills = ""
    for item in shown:
        style = (
            f' style="{conditional_escape(item["style"])}"' if item.get("style") else ""
        )
        excluded_class = " nsm-pill-excluded" if item.get("excluded") else ""
        excluded_prefix = (
            '<span class="nsm-pill-not-badge" title="Excluded (EXCEPT)">!</span>'
            if item.get("excluded")
            else ""
        )
        pills += (
            f'<a href="{conditional_escape(str(item["url"]))}"'
            f' class="nsm-rule-pill text-decoration-none{excluded_class}"{style}'
            f' title="{conditional_escape(str(item["name"]))}">'
            f'{excluded_prefix}{conditional_escape(str(item["name"]))}</a>'
        )

    if hidden:
        for item in hidden:
            item_style = (
                ("display:none;" + item["style"])
                if item.get("style")
                else "display:none"
            )
            excluded_class = " nsm-pill-excluded" if item.get("excluded") else ""
            excluded_prefix = (
                '<span class="nsm-pill-not-badge">!</span>'
                if item.get("excluded")
                else ""
            )
            pills += (
                f'<a href="{conditional_escape(str(item["url"]))}"'
                f' class="nsm-rule-pill nsm-pill-hidden text-decoration-none{excluded_class}"'
                f' style="{conditional_escape(item_style)}"'
                f' title="{conditional_escape(str(item["name"]))}">'
                f'{excluded_prefix}{conditional_escape(str(item["name"]))}</a>'
                f'<button type="button"'
                f' class="nsm-rule-pill nsm-rule-pill-muted nsm-pill-more"'
                f' style="border:none;cursor:pointer;flex-shrink:0;max-width:none;overflow:visible;"'
                f" onclick=\"var c=this.closest('.nsm-rule-pills');"
                f"c.querySelectorAll('.nsm-pill-hidden').forEach(function(e){{e.style.display='';}});"
                f'this.remove();"'
                f">+{len(hidden)}</button>"
            )

    return (
        f'<div class="nsm-rule-card">'
        f'<div class="nsm-rule-label">{conditional_escape(str(label))}</div>'
        f'<div class="nsm-rule-pills">{pills}</div>'
        f"</div>"
    )


def _rule_stack(cards):
    if not cards:
        return mark_safe('<span class="text-muted small">-</span>')
    return mark_safe(f'<div class="nsm-rule-stack">{"".join(cards)}</div>')


def _build_src_dst_cards(users=()):
    """
    Returns a list of card HTML strings for users.
    """
    type_map = OrderedDict()

    # direct users
    if users:
        type_map.setdefault("Users", []).extend(
            {"url": u.get_absolute_url(), "name": u.name} for u in users
        )

    return [_card(label, items) for label, items in type_map.items()]


def _build_src_dst_html(zones=(), users=()):
    """Backward-compatible wrapper returning full rule-stack HTML."""
    return _rule_stack(_build_src_dst_cards(zones, users))


def _custom_objects_cards(custom_objs_with_exclude):
    """Group SecurityObjects by custom_type and render as labelled cards with icons.
    Uses display_template from the custom type if set.
    custom_objs_with_exclude: list of (obj, exclude_bool) tuples."""
    type_map = OrderedDict()
    for obj, excluded in custom_objs_with_exclude:
        if obj is None:
            continue
        ct = getattr(obj, "custom_type", None)
        key = ct.name if ct is not None else type(obj).__name__
        display_name = (
            obj.render_display() if hasattr(obj, "render_display") else obj.name
        )
        type_map.setdefault(key, []).append(
            {"url": obj.get_absolute_url(), "name": display_name, "excluded": excluded}
        )
    return [_card(label, items) for label, items in type_map.items()]


# ── custom columns ────────────────────────────────────────────────────────────


def _groups_cards(groups_with_exclude):
    """Render ObjectGroup instances as a single 'Groups' card."""
    items = [
        {"url": g.get_absolute_url(), "name": g.name, "excluded": exc}
        for g, exc in groups_with_exclude
    ]
    if not items:
        return []
    return [_card("Groups", items)]


def _rule_objects(record, placement, area_slugs=None):
    allowed = set(area_slugs or [])
    out = []
    for item in record.object_items.all():
        if item.field is None:
            continue
        if item.field.placement != placement:
            continue
        if allowed and item.field.slug not in allowed:
            continue
        out.append((item.assigned_object, item.exclude))
    return out


def _rule_groups(record, placement, area_slugs=None):
    allowed = set(area_slugs or [])
    out = []
    for item in record.group_items.all():
        if item.field is None:
            continue
        if item.field.placement != placement:
            continue
        if allowed and item.field.slug not in allowed:
            continue
        out.append((item.security_group, item.exclude))
    return out


class SourceColumn(tables.Column):
    def render(self, value, record):
        cards = _build_src_dst_cards(users=record.source_users.all())
        cards += _custom_objects_cards(_rule_objects(record, "source"))
        cards += _groups_cards(_rule_groups(record, "source"))
        return _rule_stack(cards)


class DestinationColumn(tables.Column):
    def render(self, value, record):
        cards = _build_src_dst_cards(users=record.destination_users.all())
        cards += _custom_objects_cards(_rule_objects(record, "destination"))
        cards += _groups_cards(_rule_groups(record, "destination"))
        return _rule_stack(cards)


class ServiceColumn(tables.Column):
    def render(self, value, record):
        cards = _custom_objects_cards(
            _rule_objects(record, "fixed", area_slugs=("service",))
        )
        cards += _groups_cards(_rule_groups(record, "fixed", area_slugs=("service",)))
        return _rule_stack(cards)


class ActionColumn(tables.Column):
    def render(self, value, record):
        cards = _custom_objects_cards(
            _rule_objects(record, "fixed", area_slugs=("action",))
        )
        cards += _groups_cards(_rule_groups(record, "fixed", area_slugs=("action",)))
        return _rule_stack(cards)


class InfoColumn(tables.Column):
    def render(self, value, record):
        cards = _custom_objects_cards(
            _rule_objects(record, "fixed", area_slugs=("info",))
        )
        cards += _groups_cards(_rule_groups(record, "fixed", area_slugs=("info",)))
        return _rule_stack(cards)


class NameColumn(tables.Column):
    """Renders the rule name as a link; full name visible as tooltip."""

    def render(self, value, record):
        url = record.get_absolute_url()
        full = str(value)
        display = (full[:49] + "…") if len(full) > 50 else full
        return mark_safe(
            f'<a href="{conditional_escape(url)}"'
            f' title="{conditional_escape(full)}"'
            f' class="text-body">'
            f"{conditional_escape(display)}"
            f"</a>"
        )


class AssignedObjectsColumn(tables.Column):
    """Renders RulebookAssignment objects; collapses to +N when more than two."""

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

    def render(self, value):
        items = []
        for a in value.all():
            obj = a.assigned_object
            if obj is None:
                continue
            url = getattr(obj, "get_absolute_url", lambda: "#")()
            items.append((url, str(obj)))

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
    """Rulebook name with optional parent/child depth marker (NetBox prefix style)."""

    def render(self, value, record):
        if is_virtual_all_rules_rulebook(record):
            url = record.get_absolute_url()
            return format_html(
                '<a href="{}" class="nsm-rb-name-link">{}</a>',
                url,
                record.name,
            )
        url = reverse("plugins:netbox_nsm:rulebook", args=[record.pk])
        link = format_html(
            '<a href="{}" class="nsm-rb-name-link">{}</a>',
            url,
            value,
        )
        depth = rulebook_list_depth(record)
        marker = render_hierarchy_marker(depth)
        if marker:
            return format_html("{}{}", mark_safe(marker), link)
        return link


class RulebookStatusColumn(tables.Column):
    """Rulebook lifecycle status (Active, Container, Deprecated, …)."""

    def render(self, value, record):
        if is_virtual_all_rules_rulebook(record):
            return mark_safe(
                rulebook_status_badge_html(
                    "virtual",
                    label=str(_("Read-only")),
                )
            )
        return mark_safe(rulebook_status_badge_html(record.status))


class RulebookActionsColumn(ActionsColumn):
    """Hide delete when the rulebook still contains rules; offer schema copy."""

    def _has_rules(self, record) -> bool:
        rule_count = getattr(record, "rule_count", None)
        if rule_count is None:
            return record.rules.exists()
        return rule_count > 0

    def _action_names(self, record):
        """Edit is the split button; delete is added to the dropdown separately."""
        names = list(self.actions.keys())
        if "delete" in names:
            names.remove("delete")
        return names

    def _append_delete_dropdown_link(
        self,
        *,
        record,
        model,
        user,
        url_appendix: str,
        dropdown_links: list[str],
    ) -> None:
        if self._has_rules(record):
            return
        attrs = self.actions.get("delete")
        if not attrs:
            return
        permission = get_permission_for_model(model, attrs.permission)
        if attrs.permission is not None and not user.has_perm(permission):
            return
        url = get_action_url(model, action="delete", kwargs={"pk": record.pk})
        dropdown_links.append(
            f'<li><a class="dropdown-item" href="{url}{url_appendix}">'
            f'<i class="mdi mdi-{attrs.icon}"></i> {attrs.title}</a></li>'
        )

    def render(self, record, table, **kwargs):
        model = table.Meta.model
        if not isinstance(record, model) or not getattr(record, "pk", None):
            return ""

        request = getattr(table, "context", {}).get("request")
        if request:
            return_url = request.GET.get("return_url", request.get_full_path())
            url_appendix = f"?return_url={quote(return_url)}"
        else:
            url_appendix = ""

        user = getattr(request, "user", AnonymousUser())
        action_names = self._action_names(record)
        button = None
        dropdown_class = "secondary"
        dropdown_links = []

        for idx, action in enumerate(action_names):
            attrs = self.actions[action]
            permission = get_permission_for_model(model, attrs.permission)
            if attrs.permission is not None and not user.has_perm(permission):
                continue
            url = get_action_url(model, action=action, kwargs={"pk": record.pk})
            if len(action_names) == 1 or (self.split_actions and idx == 0):
                dropdown_class = attrs.css_class
                button = (
                    f'<a class="btn btn-sm btn-{attrs.css_class}" href="{url}{url_appendix}" type="button" '
                    f'aria-label="{attrs.title}">'
                    f'<i class="mdi mdi-{attrs.icon}"></i></a>'
                )
            else:
                dropdown_links.append(
                    f'<li><a class="dropdown-item" href="{url}{url_appendix}">'
                    f'<i class="mdi mdi-{attrs.icon}"></i> {attrs.title}</a></li>'
                )

        self._append_delete_dropdown_link(
            record=record,
            model=model,
            user=user,
            url_appendix=url_appendix,
            dropdown_links=dropdown_links,
        )

        if user.has_perm("netbox_nsm.add_rulebook"):
            copy_url = rulebook_schema_copy_add_url(
                record,
                return_url=request.get_full_path() if request else None,
            )
            dropdown_links.append(
                f'<li><a class="dropdown-item" href="{escape(copy_url)}">'
                f'<i class="mdi mdi-content-copy"></i> {COPY_SCHEMA_LABEL}</a></li>'
            )

        toggle_text = _("Toggle Dropdown")
        html = ""
        if self.extra_buttons:
            from django.template import Context, Template

            template = Template(self.extra_buttons)
            context = getattr(table, "context", Context())
            context.update({"record": record})
            html = template.render(context)

        if button and dropdown_links:
            html += (
                f'<span class="btn-group dropdown">'
                f"  {button}"
                f'  <a class="btn btn-sm btn-{dropdown_class} dropdown-toggle" type="button" data-bs-toggle="dropdown" '
                f'style="padding-left: 2px">'
                f'  <span class="visually-hidden">{toggle_text}</span></a>'
                f'  <ul class="dropdown-menu">{"".join(dropdown_links)}</ul>'
                f"</span>"
            )
        elif button:
            html += button
        elif dropdown_links:
            html += (
                f'<span class="btn-group dropdown">'
                f'  <a class="btn btn-sm btn-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown">'
                f'  <span class="visually-hidden">{toggle_text}</span></a>'
                f'  <ul class="dropdown-menu">{"".join(dropdown_links)}</ul>'
                f"</span>"
            )

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
        orderable=True,
        attrs={
            "th": {"style": "width: 1%; white-space: nowrap;"},
            "td": {"style": "white-space: nowrap;"},
        },
    )
    rule_count = tables.TemplateColumn(
        template_code="""
{% load i18n %}
<div class="nsm-rule-pills">
{% if record.is_virtual_all_rules %}
  <a href="{% url 'plugins:netbox_nsm:all_rules_rules' %}"
{% else %}
  <a href="{% url 'plugins:netbox_nsm:rulebook_rules' record.pk %}"
{% endif %}
     class="nsm-rule-pill nsm-rule-pill--counter nsm-rulebook-count-pill text-decoration-none"
     title="{% trans 'View rules' %}">
    {% if record.rule_count is not None %}{{ record.rule_count }}{% else %}{{ record.rules.count }}{% endif %}
  </a>
</div>
        """,
        verbose_name=_("Rules"),
        accessor="rule_count",
        orderable=True,
        attrs={
            "th": {"style": "width: 1%; white-space: nowrap;"},
            "td": {"style": "white-space: nowrap;"},
        },
    )
    platform = tables.Column(
        verbose_name=_("Platform"),
        linkify=True,
        orderable=True,
    )
    assigned_objects = AssignedObjectsColumn(accessor="assignments")
    tags = TagColumn(url_name="plugins:netbox_nsm:rulebook_list")
    actions = RulebookActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = Rulebook
        fields = (
            "id",
            "name",
            "status",
            "rule_count",
            "platform",
            "description",
            "assigned_objects",
            "tags",
        )
        default_columns = (
            "name",
            "status",
            "rule_count",
            "platform",
            "assigned_objects",
            "description",
        )


class RuleTable(NetBoxTable):
    index = tables.TemplateColumn(
        template_code="""
            <div class="nsm-rule-pills">
              <a href="{{ record.get_absolute_url }}" class="nsm-rule-pill text-decoration-none" title="{{ record.name }}">{{ record.index }}</a>
            </div>
        """,
        verbose_name=_("Index"),
        orderable=True,
        attrs={
            "th": {"style": "width: 1%; white-space: nowrap;"},
            "td": {"style": "white-space: nowrap;"},
        },
    )
    status = tables.TemplateColumn(
        template_code="""
{% load i18n %}
            {% if record.enabled %}
                <span class=\"nsm-status-icon nsm-status-icon-on\" title=\"{% trans 'On' %}\" aria-label=\"{% trans 'On' %}\">
                    <i class=\"mdi mdi-check\"></i>
                </span>
            {% else %}
                <span class=\"nsm-status-icon nsm-status-icon-off\" title=\"{% trans 'Off' %}\" aria-label=\"{% trans 'Off' %}\">
                    <i class=\"mdi mdi-close\"></i>
                </span>
            {% endif %}
        """,
        orderable=False,
        verbose_name=_("Status"),
        attrs={
            "th": {"style": "width: 1%; white-space: nowrap;"},
            "td": {"style": "white-space: nowrap;"},
        },
    )
    name = NameColumn(
        verbose_name=_("Name"),
        orderable=True,
    )
    rulebook = tables.Column(linkify=True)
    source = SourceColumn(
        orderable=False,
        verbose_name=_("Source"),
        accessor=tables.A("pk"),
    )
    destination = DestinationColumn(
        orderable=False,
        verbose_name=_("Destination"),
        accessor=tables.A("pk"),
    )
    service = ServiceColumn(
        orderable=False,
        verbose_name=_("Service"),
        accessor=tables.A("pk"),
    )
    action = ActionColumn(
        orderable=False,
        verbose_name=_("Action"),
        accessor=tables.A("pk"),
    )
    info = InfoColumn(
        orderable=False,
        verbose_name=_("Info"),
        accessor=tables.A("pk"),
    )
    tags = TagColumn(url_name="plugins:netbox_nsm:rule_list")
    actions = ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = Rule
        fields = (
            "pk",
            "id",
            "rulebook",
            "index",
            "status",
            "name",
            "source",
            "destination",
            "service",
            "action",
            "info",
            "description",
            "tags",
        )
        default_columns = (
            "pk",
            "index",
            "status",
            "name",
            "source",
            "destination",
            "service",
            "action",
            "info",
            "description",
        )


class RulebookAssignmentTable(NetBoxTable):
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
    rulebook = tables.Column(verbose_name=_("Rulebook"), linkify=True)
    actions = ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = RulebookAssignment
        fields = ("id", "rulebook", "assigned_object", "assigned_object_parent")
        default_columns = ("rulebook", "assigned_object", "assigned_object_parent")
