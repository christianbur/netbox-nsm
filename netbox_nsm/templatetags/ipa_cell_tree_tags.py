"""Template tags for IP Analyzer flat cell-tree columns."""

from django import template
from django.utils.translation import gettext as _

register = template.Library()


def _resolve_address_cidr(address_cidr, node):
    cidr = str(address_cidr or "").strip()
    if cidr:
        return cidr
    if not isinstance(node, dict):
        return ""
    cidr = str(node.get("prefix_display_cidr") or "").strip()
    if cidr:
        return cidr
    return str((node.get("ip_ref") or {}).get("str") or "").strip()


@register.simple_tag
def ipa_cell_tree_address_link_title(
    address_name,
    node=None,
    address_cidr="",
    address_status="",
    group_anchor=False,
):
    """Build native ``title`` text for Address column links."""
    name = str(address_name or "").strip()
    if not name:
        return ""

    cidr = _resolve_address_cidr(address_cidr, node)
    status = str(address_status or "").strip()
    group_name = (node or {}).get("name") if group_anchor else None

    if group_name:
        text = _("Anchor address %(name)s for group %(group)s") % {
            "name": name,
            "group": group_name,
        }
        if cidr:
            text = f"{text} · {cidr}"
        if status:
            text = f"{text} ({status})"
    elif status and cidr:
        text = _("%(name)s · %(cidr)s (%(status)s)") % {
            "name": name,
            "cidr": cidr,
            "status": status,
        }
    elif status:
        text = _("%(name)s (%(status)s)") % {"name": name, "status": status}
    elif cidr:
        text = _("%(name)s · %(cidr)s") % {"name": name, "cidr": cidr}
    else:
        text = name

    if (
        isinstance(node, dict)
        and not node.get("in_cell")
        and not node.get("is_cell_direct")
    ):
        text = f"{text} | {_('Indirect (not directly in rule cell)')}"

    return text
