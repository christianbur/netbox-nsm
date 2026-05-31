import django_tables2 as tables
from collections import OrderedDict
from django.utils.html import conditional_escape, mark_safe
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import ActionsColumn, TagColumn

from netbox_nsm.models import (
    SecurityPolicyRule,
    SecurityPolicyRulebook,
    SecurityPolicyAssignment,
)

__all__ = (
    "SecurityPolicyRulebookTable",
    "SecurityPolicyRuleTable",
    "SecurityPolicyAssignmentTable",
)


# ── helper functions for rule-stack rendering ────────────────────────────────

MAX_PILLS = 3


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
        excluded_prefix = '<span class="nsm-pill-not-badge" title="Excluded (EXCEPT)">!</span>' if item.get("excluded") else ""
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
            excluded_prefix = '<span class="nsm-pill-not-badge">!</span>' if item.get("excluded") else ""
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
        ct = obj.custom_type
        key = ct.name
        display_name = (
            obj.render_display() if hasattr(obj, "render_display") else obj.name
        )
        type_map.setdefault(key, []).append(
            {"url": obj.get_absolute_url(), "name": display_name, "excluded": excluded}
        )
    return [_card(label, items) for label, items in type_map.items()]


# ── custom columns ────────────────────────────────────────────────────────────


def _groups_cards(groups_with_exclude):
    """Render SecurityObjectGroup instances as a single 'Groups' card."""
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
        cards += _groups_cards(
            _rule_groups(record, "fixed", area_slugs=("service",))
        )
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
        return mark_safe('<span class="text-muted small">-</span>')


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


class SecurityPolicyRulebookTable(NetBoxTable):
    name = tables.LinkColumn()
    rulebook_type = tables.Column(verbose_name=_("Type"))
    tags = TagColumn(url_name="plugins:netbox_nsm:securitypolicyrulebook_list")
    actions = ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = SecurityPolicyRulebook
        fields = ("id", "name", "rulebook_type", "description", "tags")
        default_columns = ("name", "rulebook_type", "description")


class SecurityPolicyRuleTable(NetBoxTable):
    index = tables.Column(
        verbose_name=_("Index"),
        linkify=True,
        attrs={"th": {"style": "width: 1%; white-space: nowrap;"}, "td": {"style": "white-space: nowrap;"}},
    )
    status = tables.TemplateColumn(
        template_code="""
            {% if record.enabled %}
                <span class=\"nsm-status-icon nsm-status-icon-on\" title=\"Ein\" aria-label=\"Ein\">
                    <i class=\"mdi mdi-check\"></i>
                </span>
            {% else %}
                <span class=\"nsm-status-icon nsm-status-icon-off\" title=\"Aus\" aria-label=\"Aus\">
                    <i class=\"mdi mdi-close\"></i>
                </span>
            {% endif %}
        """,
        orderable=False,
        verbose_name=_("Status"),
        attrs={"th": {"style": "width: 1%; white-space: nowrap;"}, "td": {"style": "white-space: nowrap;"}},
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
    tags = TagColumn(url_name="plugins:netbox_nsm:securitypolicyrule_list")
    actions = ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = SecurityPolicyRule
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


class SecurityPolicyAssignmentTable(NetBoxTable):
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
        model = SecurityPolicyAssignment
        fields = ("id", "rulebook", "assigned_object", "assigned_object_parent")
        default_columns = ("rulebook", "assigned_object", "assigned_object_parent")
