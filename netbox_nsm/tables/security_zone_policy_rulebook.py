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

MAX_PILLS = 4


def _card(label, items, max_pills=MAX_PILLS):
    """
    items: list of dicts with keys 'url', 'name', and optional 'style'.
    Returns an nsm-rule-card HTML string.
    First MAX_PILLS are shown; the rest are hidden behind a clickable +N badge.
    """
    shown = items[:max_pills]
    hidden = items[max_pills:]

    pills = ""
    for item in shown:
        style = f' style="{conditional_escape(item["style"])}"' if item.get("style") else ""
        pills += (
            f'<a href="{conditional_escape(str(item["url"]))}"'
            f' class="nsm-rule-pill text-decoration-none"{style}>'
            f'{conditional_escape(str(item["name"]))}</a>'
        )

    if hidden:
        # hidden pills – wrapped in a span with display:contents so they
        # participate in the flex row once visible
        hidden_html = ""
        for item in hidden:
            style = f' style="{conditional_escape(item["style"])}"' if item.get("style") else ""
            hidden_html += (
                f'<a href="{conditional_escape(str(item["url"]))}"'
                f' class="nsm-rule-pill text-decoration-none"{style}>'
                f'{conditional_escape(str(item["name"]))}</a>'
            )
        pills += (
            f'<span class="nsm-pills-overflow" style="display:none;contents:none">'
            f'{hidden_html}</span>'
            f'<button type="button"'
            f' class="nsm-rule-pill nsm-rule-pill-muted"'
            f' style="border:none;cursor:pointer;"'
            f' onclick="'
            f'var s=this.previousElementSibling;'
            f's.style.display=\'contents\';'
            f'this.style.display=\'none\';"'
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


def _build_src_dst_cards(groups, zones=(), addresses=(), users=()):
    """
    Clusters ObjectGroups by their type label into one card per type.
    Direct addresses/zones/users are merged into the same label bucket.
    Returns a list of card HTML strings.
    """
    type_map = OrderedDict()

    # source_groups / destination_groups → cluster by type label
    for grp in groups:
        label = grp.get_display_member_type_label()
        type_map.setdefault(label, []).append(
            {"url": grp.get_absolute_url(), "name": grp.name}
        )

    # direct addresses → merge into "Addresses" bucket (or create it)
    if addresses:
        type_map.setdefault("Addresses", []).extend(
            {"url": addr.get_absolute_url(), "name": addr.name}
            for addr in addresses
        )

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


def _build_src_dst_html(groups, zones=(), addresses=(), users=()):
    """Backward-compatible wrapper returning full rule-stack HTML."""
    return _rule_stack(_build_src_dst_cards(groups, zones, addresses, users))


def _custom_objects_cards(custom_objs):
    """Group ObjectCustomObjects by custom_type and render as labelled cards with icons."""
    type_map = OrderedDict()
    for obj in custom_objs:
        ct = obj.custom_type
        key = ct.name
        type_map.setdefault(key, []).append(
            {"url": obj.get_absolute_url(), "name": obj.name}
        )
    return [
        _card(label, items)
        for label, items in type_map.items()
    ]


# ── custom columns ────────────────────────────────────────────────────────────

class SourceColumn(tables.Column):
    def render(self, value, record):
        cards = _build_src_dst_cards(
            groups=record.source_groups.all(),
            zones=record.source_zones.all(),
            addresses=record.source_addresses.all(),
            users=record.source_users.all(),
        )
        cards += _custom_objects_cards(record.custom_srcdst_objects.all())
        return _rule_stack(cards)


class DestinationColumn(tables.Column):
    def render(self, value, record):
        cards = _build_src_dst_cards(
            groups=record.destination_groups.all(),
            zones=record.destination_zones.all(),
            addresses=record.destination_addresses.all(),
            users=record.destination_users.all(),
        )
        cards += _custom_objects_cards(record.custom_srcdst_objects.all())
        return _rule_stack(cards)


class ServiceColumn(tables.Column):
    def render(self, value, record):
        type_map = OrderedDict()
        svcs = list(record.services.all())
        if svcs:
            type_map["Services"] = [{"url": s.get_absolute_url(), "name": s.name} for s in svcs]
        apps = list(record.applications.all())
        if apps:
            type_map["Applications"] = [{"url": a.get_absolute_url(), "name": a.name} for a in apps]
        appsets = list(record.application_sets.all())
        if appsets:
            type_map["App. Sets"] = [{"url": a.get_absolute_url(), "name": a.name} for a in appsets]
        cards = [_card(label, items) for label, items in type_map.items()]
        cards += _custom_objects_cards(record.custom_service_objects.all())
        return _rule_stack(cards)


class ActionColumn(tables.Column):
    def render(self, value, record):
        action_display = record.get_policy_action_display()
        action_pill = (
            f'<span class="nsm-rule-pill nsm-rule-pill-accent">'
            f'{conditional_escape(action_display)}</span>'
        )
        log_pill = (
            '<span class="nsm-rule-pill nsm-rule-pill-success">Enabled</span>'
            if record.log_enabled
            else '<span class="nsm-rule-pill nsm-rule-pill-muted">Disabled</span>'
        )
        cards = [
            (f'<div class="nsm-rule-card">'
             f'<div class="nsm-rule-label">Action</div>'
             f'<div class="nsm-rule-pills">{action_pill}</div>'
             f'</div>'),
            (f'<div class="nsm-rule-card">'
             f'<div class="nsm-rule-label">Log</div>'
             f'<div class="nsm-rule-pills">{log_pill}</div>'
             f'</div>'),
        ]
        cards += _custom_objects_cards(record.custom_action_objects.all())
        return _rule_stack([mark_safe(c) for c in cards])


class InfoColumn(tables.Column):
    def render(self, value, record):
        cards = []
        comments = list(record.object_comment.all())
        if comments:
            cards.append(_card(
                "Comment",
                [{"url": c.get_absolute_url(), "name": c.name} for c in comments],
            ))
        installed = list(record.object_installed_on.all())
        if installed:
            cards.append(_card(
                "Installed On",
                [{"url": i.get_absolute_url(), "name": i.name} for i in installed],
            ))
        return _rule_stack(cards)


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
    index = tables.Column(verbose_name=_("Index"))
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
    name = tables.LinkColumn()
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
