"""Diff-fund markers and name-pill enrichment for address diff."""
from __future__ import annotations

import netbox_nsm.analysis._lazy_api as _hub
from netbox_nsm.analysis.addr_diff_collect import (
    _addr_append_leaf_source,
    _addr_leaf_source_object,
    _addr_source_name_set,
)

def _addr_side_has_name_conflict(entry):
    """True when one side resolves the same IPAM key via multiple object names."""
    return len(_addr_source_name_set(entry)) > 1


def _addr_cross_side_name_conflict(entry_a, entry_b):
    """True when both sides share an IPAM key but with different object names."""
    names_a = _addr_source_name_set(entry_a)
    names_b = _addr_source_name_set(entry_b)
    if not names_a or not names_b:
        return False
    return names_a != names_b


def _addr_diff_fund_detail(entry, *, other_entry=None, label_a="", label_b=""):
    """Build tooltip payload for a diff fund marker."""
    names_a = sorted(_addr_source_name_set(entry))
    if other_entry is None:
        if len(names_a) < 2:
            return None
        return {"same_side": True, "names": names_a}
    names_b = sorted(_addr_source_name_set(other_entry))
    if names_a == names_b and len(names_a) <= 1:
        return None
    detail = {
        "names_a": names_a,
        "names_b": names_b,
        "label_a": str(label_a),
        "label_b": str(label_b),
    }
    if _addr_side_has_name_conflict(entry):
        detail["same_side_a"] = True
    if _addr_side_has_name_conflict(other_entry):
        detail["same_side_b"] = True
    return detail


def _addr_diff_fund_tooltip(detail):
    """Human-readable tooltip for a diff fund marker."""
    from django.utils.translation import gettext as _

    if not detail:
        return str(_("Same IP address/range/prefix, but different object names"))
    if detail.get("same_side"):
        names = ", ".join(detail.get("names") or [])
        return str(
            _("Same IP address/range/prefix linked to multiple object names: %(names)s")
            % {"names": names}
        )
    if detail.get("multi_side"):
        parts = []
        for side in detail.get("sides") or []:
            names = ", ".join(side.get("names") or [])
            parts.append(f"{side.get('label') or '?'}: {names}")
        return str(
            _(
                "Same IP address/range/prefix, but different object names "
                "(%(details)s)"
            )
            % {"details": "; ".join(parts)}
        )
    names_a = ", ".join(detail.get("names_a") or [])
    names_b = ", ".join(detail.get("names_b") or [])
    return str(
        _(
            "Same IP address/range/prefix, but different object names "
            "(%(side_a)s: %(names_a)s; %(side_b)s: %(names_b)s)"
        )
        % {
            "side_a": detail.get("label_a") or "A",
            "side_b": detail.get("label_b") or "B",
            "names_a": names_a,
            "names_b": names_b,
        }
    )


def _addr_diff_fund_detail_multi(entries, labels):
    """Tooltip payload when an IPAM key differs across multiple diff sides."""
    sides = []
    for index, entry in enumerate(entries):
        if not entry:
            continue
        names = sorted(_addr_source_name_set(entry))
        if not names:
            continue
        label = labels[index] if index < len(labels) else str(index + 1)
        sides.append({"label": str(label), "names": names})
    if not sides:
        return None
    if len(sides) == 1 and len(sides[0]["names"]) < 2:
        return None
    if len(sides) == 1:
        return {"same_side": True, "names": sides[0]["names"]}
    return {
        "multi_side": True,
        "sides": sides,
        "label_a": sides[0]["label"],
        "label_b": sides[1]["label"],
        "names_a": sides[0]["names"],
        "names_b": sides[1]["names"],
    }


def _addr_entries_is_diff_fund(entries, labels):
    """Whether entries for one IPAM key should be flagged as a diff fund."""
    entries = [entry for entry in entries if entry]
    if not entries:
        return False, None
    for entry in entries:
        if _addr_side_has_name_conflict(entry):
            return True, _addr_diff_fund_detail_multi(entries, labels)
    name_sets = [_addr_source_name_set(entry) for entry in entries]
    unique_sets = {frozenset(name_set) for name_set in name_sets}
    if len(unique_sets) > 1:
        return True, _addr_diff_fund_detail_multi(entries, labels)
    return False, None


def _addr_entry_is_diff_fund(entry, *, other_entry=None, label_a="", label_b=""):
    """Whether this IPAM key should be flagged as a diff fund."""
    if _addr_side_has_name_conflict(entry):
        return True
    if other_entry is not None and _addr_cross_side_name_conflict(entry, other_entry):
        return True
    return False


def _enrich_diff_name_pill_fields(node, entry, *, other_entry=None, diff_status):
    """Add diff_name_a/b, diff_url_a/b, diff_same_name for two-color name pills."""
    name = str(entry.get("name") or "").strip()
    url = entry.get("url") or "#"

    if diff_status == "only_a":
        node["diff_name_a"] = name
        node["diff_url_a"] = url
        node["diff_same_name"] = True
        return
    if diff_status == "only_b":
        node["diff_name_b"] = name
        node["diff_url_b"] = url
        node["diff_same_name"] = True
        return

    if other_entry is None:
        node["diff_name_a"] = name
        node["diff_url_a"] = url
        node["diff_same_name"] = True
        return

    other_name = str(other_entry.get("name") or "").strip()
    other_url = other_entry.get("url") or "#"
    names_a = _addr_source_name_set(entry)
    names_b = _addr_source_name_set(other_entry)
    if names_a == names_b and len(names_a) <= 1:
        node["diff_same_name"] = True
        node["diff_name_a"] = name or other_name
        node["diff_url_a"] = url
    else:
        node["diff_same_name"] = False
        node["diff_name_a"] = name
        node["diff_url_a"] = url
        node["diff_name_b"] = other_name
        node["diff_url_b"] = other_url


def _diff_cell_address_refs(node, entry=None):
    """Build ADDRESS pill refs for IPA diff rows."""
    refs = []
    if not node.get("diff_same_name") and node.get("diff_name_a") and node.get("diff_name_b"):
        refs.append(
            {
                "name": node["diff_name_a"],
                "url": node.get("diff_url_a") or node.get("url") or "#",
            }
        )
        refs.append(
            {
                "name": node["diff_name_b"],
                "url": node.get("diff_url_b") or node.get("url") or "#",
            }
        )
        return refs, True
    if node.get("diff_name_a"):
        return (
            [
                {
                    "name": node["diff_name_a"],
                    "url": node.get("diff_url_a") or node.get("url") or "#",
                }
            ],
            False,
        )
    if node.get("diff_name_b"):
        return (
            [
                {
                    "name": node["diff_name_b"],
                    "url": node.get("diff_url_b") or node.get("url") or "#",
                }
            ],
            False,
        )
    for src in (entry or {}).get("source_objects") or []:
        name = str(src.get("name") or "").strip()
        if name:
            refs.append({"name": name, "url": src.get("url") or "#"})
    if not refs:
        name = str(node.get("name") or "").strip()
        if name:
            refs.append({"name": name, "url": node.get("url") or "#"})
    return refs, len(refs) > 1


def _enrich_diff_cell_pill_fields(node, *, entry=None):
    """Attach IPA cell ADDRESS pill metadata to diff tree nodes."""
    if node.get("diff_fund"):
        return node
    refs, multi = _diff_cell_address_refs(node, entry)
    if not refs:
        return node
    node["is_cell_direct"] = True
    node["cell_addresses"] = refs
    if multi:
        node["cell_addresses_multi"] = True
    else:
        node.pop("cell_addresses_multi", None)
    return node


def _shallow_addr_leaf_for_diff(
    node,
    *,
    diff_status,
    diff_fund=False,
    fund_detail=None,
    other_entry=None,
    diff_present_labels=None,
):
    """Return a display leaf with diff_status for grouped diff output."""
    leaf = {
        "kind": "leaf",
        "name": node.get("name") or "",
        "url": node.get("url") or "#",
        "ip_ref": node.get("ip_ref"),
        "prefix_display_cidr": node.get("prefix_display_cidr"),
        "prefix_display_netmask": node.get("prefix_display_netmask"),
        "related_refs": node.get("related_refs"),
        "diff_status": diff_status,
        "children": [],
    }
    if diff_present_labels:
        leaf["diff_present_labels"] = list(diff_present_labels)
    _enrich_diff_name_pill_fields(
        leaf, node, other_entry=other_entry, diff_status=diff_status
    )
    _enrich_diff_cell_pill_fields(leaf, entry=node)
    if diff_fund:
        leaf["diff_fund"] = True
        if fund_detail:
            leaf["fund_detail"] = fund_detail
            leaf["fund_tooltip"] = _addr_diff_fund_tooltip(fund_detail)
    _hub._enrich_addr_tree_copy_lines(leaf)
    return leaf

