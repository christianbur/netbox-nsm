import django_tables2 as tables
from collections import OrderedDict
from django.utils.html import conditional_escape, mark_safe
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import ActionsColumn, TagColumn

from netbox_nsm.models import (
    SecurityZonePolicyRule,
    SecurityZonePolicyRulebook,
    SecurityZonePolicyRulebookAssignment,
)

__all__ = (
    "SecurityZonePolicyRulebookTable",
    "SecurityZonePolicyRuleTable",
    "SecurityZonePolicyRulebookAssignmentTable",
)


# ── helper functions for rule-stack rendering ────────────────────────────────

MAX_PILLS = 3


def _card(label, items, max_pills=MAX_PILLS):
    """
    items: list of dicts with keys 'url', 'name', and optional 'style'.
    Returns an nsm-rule-card HTML string.
    First max_pills are shown; the rest collapse to a hoverable +N badge.
    """
    shown = items[:max_pills]
    hidden = items[max_pills:]

    pills = ""
    for item in shown:
        style = f' style="{conditional_escape(item["style"])}"' if item.get("style") else ""
        pills += (
            f'<a href="{conditional_escape(str(item["url"]))}"'
            f' class="nsm-rule-pill text-decoration-none"{style}'
            f' title="{conditional_escape(str(item["name"]))}">'            
            f'{conditional_escape(str(item["name"]))}</a>'
        )

    if hidden:
        for item in hidden:
            item_style = ("display:none;" + item["style"]) if item.get("style") else "display:none"
            pills += (
                f'<a href="{conditional_escape(str(item["url"]))}"'
                f' class="nsm-rule-pill nsm-pill-hidden text-decoration-none"'
                f' style="{conditional_escape(item_style)}"'
                f' title="{conditional_escape(str(item["name"]))}">'
                f'{conditional_escape(str(item["name"]))}</a>'
            )
        pills += (
            f'<button type="button"'
            f' class="nsm-rule-pill nsm-rule-pill-muted nsm-pill-more"'
            f' style="border:none;cursor:pointer;flex-shrink:0;max-width:none;overflow:visible;"'
            f' onclick="var c=this.closest(\'.nsm-rule-pills\');'
            f'c.querySelectorAll(\'.nsm-pill-hidden\').forEach(function(e){{e.style.display=\'\';}});'
            f'this.remove();"'
            f'>+{len(hidden)}</button>'
        )

    return (
        f'<div class="nsm-rule-card">'
        f'<div class="nsm-rule-label">{conditional_escape(str(label))}</div>'
        f'<div class="nsm-rule-pills">{pills}</div>'
        f'</div>'
    )


def _rule_stack(cards):
    if not cards:
        return mark_safe('<span class="text-muted small">-</span>')
    return mark_safe(f'<div class="nsm-rule-stack">{"".join(cards)}</div>')


def _build_src_dst_cards(zones=(), users=()):
    """
    Returns a list of card HTML strings for zones and users.
    """
    type_map = OrderedDict()

    # direct zones (coloured pills)
    if zones:
        type_map.setdefault("Zones", []).extend(
            {
                "url": z.get_absolute_url(),
                "name": z.name,
                "style": f"background-color: {z.color}; color: #fff;",
            }
            for z in zones
        )

    # direct users
    if users:
        type_map.setdefault("Users", []).extend(
            {"url": u.get_absolute_url(), "name": u.name} for u in users
        )

    return [_card(label, items) for label, items in type_map.items()]


def _build_src_dst_html(zones=(), users=()):
    """Backward-compatible wrapper returning full rule-stack HTML."""
    return _rule_stack(_build_src_dst_cards(zones, users))


def _custom_objects_cards(custom_objs):
    """Group ObjectCustomObjects by custom_type and render as labelled cards with icons.
    Uses display_template from the custom type if set."""
    type_map = OrderedDict()
    for obj in custom_objs:
        ct = obj.custom_type
        key = ct.name
        display_name = obj.render_display() if hasattr(obj, "render_display") else obj.name
        type_map.setdefault(key, []).append(
            {"url": obj.get_absolute_url(), "name": display_name}
        )
    return [
        _card(label, items)
        for label, items in type_map.items()
    ]


# ── custom columns ────────────────────────────────────────────────────────────

def _groups_cards(groups):
    """Render ObjectGroup instances as a single 'Groups' card."""
    items = [
        {"url": g.get_absolute_url(), "name": g.name}
        for g in groups
    ]
    if not items:
        return []
    return [_card("Groups", items)]


class SourceColumn(tables.Column):
    def render(self, value, record):
        cards = _build_src_dst_cards(zones=record.source_zones.all())
        cards += _custom_objects_cards(record.custom_srcdst_objects.all())
        cards += _groups_cards(record.source_groups.all())
        return _rule_stack(cards)


class DestinationColumn(tables.Column):
    def render(self, value, record):
        cards = _build_src_dst_cards(zones=record.destination_zones.all())
        cards += _custom_objects_cards(record.destination_custom_objects.all())
        cards += _groups_cards(record.destination_groups.all())
        return _rule_stack(cards)


class ServiceColumn(tables.Column):
    def render(self, value, record):
        cards = _custom_objects_cards(record.custom_service_objects.all())
        cards += _groups_cards(record.service_groups.all())
        return _rule_stack(cards)


class ActionColumn(tables.Column):
    def render(self, value, record):
        cards = _custom_objects_cards(record.custom_action_objects.all())
        cards += _groups_cards(record.action_groups.all())
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
            f'{conditional_escape(display)}'
            f'</a>'
        )


class SecurityZonePolicyRulebookTable(NetBoxTable):
    name = tables.LinkColumn()
    rulebook_type = tables.Column(verbose_name=_("Type"))
    tags = TagColumn(url_name="plugins:netbox_nsm:securityzonepolicyrulebook_list")
    actions = ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = SecurityZonePolicyRulebook
        fields = ("id", "name", "rulebook_type", "description", "tags")
        default_columns = ("name", "rulebook_type", "description")


class SecurityZonePolicyRuleTable(NetBoxTable):
    index = tables.Column(
        verbose_name=mark_safe('<i class="mdi mdi-pound" title="Index" aria-label="Index" style="color:inherit"></i>'),
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
    tags = TagColumn(url_name="plugins:netbox_nsm:securityzonepolicyrule_list")
    actions = ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = SecurityZonePolicyRule
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
        )


class SecurityZonePolicyRulebookAssignmentTable(NetBoxTable):
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
        model = SecurityZonePolicyRulebookAssignment
        fields = ("id", "rulebook", "assigned_object", "assigned_object_parent")
        default_columns = ("rulebook", "assigned_object", "assigned_object_parent")
