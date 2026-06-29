
"""IPAM prefix drilldown, stats, and lazy category loading."""
from __future__ import annotations
from django.utils.html import conditional_escape
import netbox_nsm.analyzers.ip._lazy_api as _hub
from netbox_nsm.core.api_urls import get_api_url_for_content_type as _get_api_url_for_content_type

_IPAM_ADDR_MODEL_NAMES = frozenset({"prefix", "ipaddress", "iprange"})
_IPAM_PREFIX_CHILDREN_MAX = 250
_IPAM_PREFIX_LARGE_CHILD_THRESHOLD = 50
_IPAM_PREFIX_LARGE_IP_THRESHOLD = 1000


def _prefix_is_large(stats):
    """True when eager tree expansion would be too expensive."""
    if not stats:
        return False
    child_count = int((stats.get("child_prefixes") or {}).get("count") or 0)
    ip_count = int((stats.get("ip_addresses") or {}).get("count") or 0)
    return (
        child_count > _IPAM_PREFIX_LARGE_CHILD_THRESHOLD
        or ip_count > _IPAM_PREFIX_LARGE_IP_THRESHOLD
    )


def _ipam_analyzer_stat_label(kind):
    from django.utils.translation import gettext as _

    labels = {
        "child_prefixes": _("IPAM > Prefixes"),
        "ip_addresses": _("IPAM > IP Addresses"),
        "ip_ranges": _("IPAM > IP Ranges"),
        "nsm_addresses": _("Custom Objects > Addresses"),
    }
    return str(labels[kind])


def _prefix_ipam_stats(prefix):
    """NetBox-native prefix inventory counts (same sources as the prefix detail tabs)."""
    from django.urls import reverse

    from netbox_nsm.addresses.address_ipam_fk import (
        addresses_for_ipam_object_queryset,
        get_nsm_address_model,
    )

    stats = {
        "child_prefixes": {
            "kind": "child_prefixes",
            "label": _ipam_analyzer_stat_label("child_prefixes"),
            "count": prefix.get_child_prefixes().count(),
            "url": reverse("ipam:prefix_prefixes", kwargs={"pk": prefix.pk}),
        },
        "ip_addresses": {
            "kind": "ip_addresses",
            "label": _ipam_analyzer_stat_label("ip_addresses"),
            "count": prefix.get_child_ips().count(),
            "url": reverse("ipam:prefix_ipaddresses", kwargs={"pk": prefix.pk}),
        },
        "ip_ranges": {
            "kind": "ip_ranges",
            "label": _ipam_analyzer_stat_label("ip_ranges"),
            "count": prefix.get_child_ranges().count(),
            "url": reverse("ipam:prefix_ipranges", kwargs={"pk": prefix.pk}),
        },
    }
    addr_model = get_nsm_address_model()
    if addr_model is not None:
        addr_count = addresses_for_ipam_object_queryset(addr_model, prefix).count()
        if addr_count:
            stats["nsm_addresses"] = {
                "kind": "nsm_addresses",
                "label": _ipam_analyzer_stat_label("nsm_addresses"),
                "count": addr_count,
                "url": prefix.get_absolute_url(),
            }
    return stats


def _ordered_ipam_stats(stats):
    order = ("child_prefixes", "ip_addresses", "ip_ranges", "nsm_addresses")
    ordered = []
    for key in order:
        if key not in stats:
            continue
        item = dict(stats[key])
        item.setdefault("kind", key)
        item.setdefault("label", _ipam_analyzer_stat_label(key))
        ordered.append(item)
    return ordered


def _ipam_stats_short(stats_list):
    """Compact summary: child-prefixes / ips / ranges / nsm-addresses counts."""
    return "/".join(str(item.get("count", 0)) for item in stats_list)


def _ipam_stats_total(stats_list):
    """Sum all NetBox ipam_stats category counts (matches pill segments)."""
    return sum(int(item.get("count") or 0) for item in (stats_list or []))


def _ipam_stats_ip_count(stats_list):
    """Return NetBox IP-address count from ordered ipam_stats."""
    for item in stats_list or []:
        if item.get("kind") == "ip_addresses":
            return int(item.get("count") or 0)
    for item in stats_list or []:
        label = str(item.get("label") or "")
        if "IP Addresses" in label or "IP-Adressen" in label:
            return int(item.get("count") or 0)
    return 0


def _ipam_stats_subnet_count(stats_list):
    """Return NetBox child-prefix count from ordered ipam_stats."""
    for item in stats_list or []:
        if item.get("kind") == "child_prefixes":
            return int(item.get("count") or 0)
    for item in stats_list or []:
        label = str(item.get("label") or "")
        if "Prefixes" in label or "Prefixe" in label:
            return int(item.get("count") or 0)
    return 0


def _ipam_stats_range_count(stats_list):
    """Return NetBox IP-range count from ordered ipam_stats."""
    for item in stats_list or []:
        if item.get("kind") == "ip_ranges":
            return int(item.get("count") or 0)
    for item in stats_list or []:
        label = str(item.get("label") or "")
        if "IP Ranges" in label or "IP-Bereiche" in label:
            return int(item.get("count") or 0)
    return 0


def _attach_ipam_stats_meta(node, stats, *, truncated=None):
    ordered = _ordered_ipam_stats(stats) if isinstance(stats, dict) else list(stats)
    node["ipam_stats"] = ordered
    node["ipam_stats_short"] = _ipam_stats_short(ordered)
    if truncated is not None:
        node["ipam_truncated"] = any(truncated.values())
    return node


def _attach_prefix_ipam_meta(node, prefix, *, stats=None, truncated=None):
    """Attach NetBox prefix tab counts for the analyzer UI."""
    if stats is None:
        stats = _hub._prefix_ipam_stats(prefix)
    return _attach_ipam_stats_meta(node, stats, truncated=truncated)


def _lookup_ipam_prefix_from_ip_ref(ip_ref):
    """Resolve a NetBox Prefix from an analyzer ``ip_ref`` payload."""
    if not ip_ref:
        return None
    from django.contrib.contenttypes.models import ContentType
    from ipam.models import Prefix

    from netbox_nsm.analyzers.ip.addr_constants import FIELD_TYPE_LABELS

    ct_raw = ip_ref.get("ct")
    pk_raw = ip_ref.get("pk")
    if str(ct_raw or "").isdigit() and str(pk_raw or "").isdigit():
        try:
            ct = ContentType.objects.get(pk=int(ct_raw))
            if ct.app_label == "ipam" and ct.model == "prefix":
                return Prefix.objects.filter(pk=int(pk_raw)).first()
        except Exception:
            pass
    if ip_ref.get("type") == FIELD_TYPE_LABELS["prefix"]:
        return _hub._lookup_ipam_prefix_for_cidr(ip_ref.get("str"))
    cidr = str(ip_ref.get("str") or "").strip()
    if cidr and "/" in cidr:
        return _hub._lookup_ipam_prefix_for_cidr(cidr)
    return None


def _lookup_ipam_range_from_ip_ref(ip_ref):
    """Resolve a NetBox IPRange from an analyzer ``ip_ref`` payload."""
    if not ip_ref:
        return None
    from django.contrib.contenttypes.models import ContentType
    from ipam.models import IPRange

    from netbox_nsm.analyzers.ip.addr_constants import FIELD_TYPE_LABELS

    ct_raw = ip_ref.get("ct")
    pk_raw = ip_ref.get("pk")
    if str(ct_raw or "").isdigit() and str(pk_raw or "").isdigit():
        try:
            ct = ContentType.objects.get(pk=int(ct_raw))
            if ct.app_label == "ipam" and ct.model == "iprange":
                return IPRange.objects.filter(pk=int(pk_raw)).first()
        except Exception:
            pass
    cidr = str(ip_ref.get("str") or "")
    if ip_ref.get("type") == FIELD_TYPE_LABELS["range"] or "–" in cidr or "-" in cidr:
        if "–" in cidr or "-" in cidr:
            try:
                from ipam.models import IPRange as _IPRange

                sep = "–" if "–" in cidr else "-"
                start, end = (part.strip() for part in cidr.split(sep, 1))
                return (
                    _IPRange.objects.filter(
                        start_address=start, end_address=end
                    )
                    .order_by("pk")
                    .first()
                )
            except Exception:
                pass
    return None


def _resolve_ipam_stats_from_ip_ref(ip_ref):
    """Return raw IPAM inventory stats for a prefix or range ref (never host IPs)."""
    from netbox_nsm.analyzers.ip.addr_constants import FIELD_TYPE_LABELS

    if not ip_ref:
        return None
    ref_type = ip_ref.get("type")
    if ref_type in (FIELD_TYPE_LABELS["prefix"], None):
        prefix = _lookup_ipam_prefix_from_ip_ref(ip_ref)
        if prefix is not None:
            return _prefix_ipam_stats(prefix)
    if ref_type in (FIELD_TYPE_LABELS["range"], None):
        ip_range = _lookup_ipam_range_from_ip_ref(ip_ref)
        if ip_range is not None:
            return _ipam_range_stats(ip_range)
    return None


def _ip_count_from_ip_ref(ip_ref):
    """Direct IP total from the linked IPAM prefix or range (0 for host-only refs)."""
    stats = _resolve_ipam_stats_from_ip_ref(ip_ref)
    if not stats:
        return 0
    return _ipam_stats_ip_count(_ordered_ipam_stats(stats))


def _collect_ipam_prefix_children_impl(prefix, *, include_nsm_addresses=True):
    """Load a bounded preview tree grouped by NetBox category."""
    from netbox_nsm.addresses.address_ipam_fk import (
        addresses_for_ipam_object_queryset,
        get_nsm_address_model,
    )

    limit = _IPAM_PREFIX_CHILDREN_MAX
    stats = _hub._prefix_ipam_stats(prefix)
    if not include_nsm_addresses:
        stats = {key: value for key, value in stats.items() if key != "nsm_addresses"}
    truncated = {}

    if _prefix_is_large(stats):
        for key in ("child_prefixes", "ip_addresses", "ip_ranges"):
            if key in stats:
                truncated[key] = int(stats[key].get("count") or 0) > 0
        if include_nsm_addresses and "nsm_addresses" in stats:
            truncated["nsm_addresses"] = (
                int(stats["nsm_addresses"].get("count") or 0) > 0
            )
        for key, flag in truncated.items():
            if key in stats:
                stats[key]["truncated"] = flag
        grouped = {
            "child_prefixes": [],
            "ip_addresses": [],
            "ip_ranges": [],
            "nsm_addresses": [],
        }
        return grouped, stats, truncated

    child_prefixes = list(prefix.get_child_prefixes().order_by("prefix", "pk")[:limit])
    truncated["child_prefixes"] = stats["child_prefixes"]["count"] > len(
        child_prefixes
    )

    ip_count = stats["ip_addresses"]["count"]
    child_ips = (
        list(prefix.get_child_ips().order_by("address", "pk")[:limit])
        if ip_count <= limit
        else []
    )
    truncated["ip_addresses"] = ip_count > len(child_ips)

    range_count = stats["ip_ranges"]["count"]
    child_ranges = (
        list(prefix.get_child_ranges().order_by("start_address", "pk")[:limit])
        if range_count <= limit
        else []
    )
    truncated["ip_ranges"] = range_count > len(child_ranges)

    child_addrs = []
    if include_nsm_addresses:
        addr_model = get_nsm_address_model()
        if addr_model is not None:
            addr_qs = addresses_for_ipam_object_queryset(addr_model, prefix)
            addr_count = addr_qs.count()
            if addr_count:
                if "nsm_addresses" not in stats:
                    stats["nsm_addresses"] = {
                        "label": _ipam_analyzer_stat_label("nsm_addresses"),
                        "count": addr_count,
                        "url": prefix.get_absolute_url(),
                    }
                if addr_count <= limit:
                    child_addrs = list(addr_qs.order_by("name")[:limit])
                truncated["nsm_addresses"] = addr_count > len(child_addrs)

    for key, flag in truncated.items():
        if key in stats:
            stats[key]["truncated"] = flag

    grouped = {
        "child_prefixes": child_prefixes,
        "ip_addresses": child_ips,
        "ip_ranges": child_ranges,
        "nsm_addresses": child_addrs,
    }
    return grouped, stats, truncated


def _flatten_ipam_grouped(grouped):
    order = ("child_prefixes", "ip_addresses", "ip_ranges", "nsm_addresses")
    items = []
    for key in order:
        items.extend(grouped.get(key) or [])
    return items


def _query_ipam_category_objects(prefix, category, *, offset=0, limit=None):
    """Fetch one page of objects for a prefix inventory category."""
    from netbox_nsm.addresses.address_ipam_fk import (
        addresses_for_ipam_object_queryset,
        get_nsm_address_model,
    )

    page_size = limit if limit is not None else _IPAM_PREFIX_CHILDREN_MAX
    page_size = min(max(int(page_size), 1), _IPAM_PREFIX_CHILDREN_MAX)
    offset = max(int(offset), 0)
    end = offset + page_size

    if category == "child_prefixes":
        return list(
            prefix.get_child_prefixes().order_by("prefix", "pk")[offset:end]
        )
    if category == "ip_addresses":
        return list(prefix.get_child_ips().order_by("address", "pk")[offset:end])
    if category == "ip_ranges":
        return list(
            prefix.get_child_ranges().order_by("start_address", "pk")[offset:end]
        )
    if category == "nsm_addresses":
        addr_model = get_nsm_address_model()
        if addr_model is None:
            return []
        return list(
            addresses_for_ipam_object_queryset(addr_model, prefix)
            .order_by("name")[offset:end]
        )
    return []


def _query_ipam_range_ip_objects(ip_range, *, offset=0, limit=None):
    """Fetch one page of IP addresses contained in an IPAM range."""
    from ipam.models import IPAddress

    page_size = limit if limit is not None else _IPAM_PREFIX_CHILDREN_MAX
    page_size = min(max(int(page_size), 1), _IPAM_PREFIX_CHILDREN_MAX)
    offset = max(int(offset), 0)
    end = offset + page_size
    start = ip_range.start_address
    end_addr = ip_range.end_address
    return list(
        IPAddress.objects.filter(address__gte=start, address__lte=end_addr)
        .order_by("address", "pk")[offset:end]
    )


def _filter_ipam_drilldown_category_nodes(nodes):
    """Drop NSM-address mirror categories from prefix drill-down (show IPAM only)."""
    filtered = []
    for node in nodes or []:
        ctx = node.get("lazy_ctx") or {}
        if ctx.get("category") == "nsm_addresses":
            continue
        filtered.append(node)
    return filtered


def _ipam_range_ip_count(ip_range) -> int:
    """Count IP addresses contained in an IPAM range."""
    from ipam.models import IPAddress

    start = ip_range.start_address
    end = ip_range.end_address
    return IPAddress.objects.filter(address__gte=start, address__lte=end).count()


def _ipam_range_stats(ip_range) -> dict:
    """IPAM range inventory for analyzer badges (IP count from NetBox)."""
    from django.urls import reverse

    ip_count = _ipam_range_ip_count(ip_range)
    return {
        "ip_addresses": {
            "kind": "ip_addresses",
            "label": _ipam_analyzer_stat_label("ip_addresses"),
            "count": ip_count,
            "url": reverse("ipam:iprange_ipaddresses", kwargs={"pk": ip_range.pk}),
        },
    }


def _build_ipam_lazy_batch_node(parent, *, category, count, loaded, stats, lazy_ctx):
    """Lazy-load placeholder for a prefix or range inventory slice."""
    stat = (stats or {}).get(category) or {}
    url = stat.get("url") or getattr(parent, "get_absolute_url", lambda: "#")()
    return {
        "kind": "lazy_batch",
        "name": stat.get("label") or _ipam_analyzer_stat_label(category),
        "url": url,
        "count": int(count or 0),
        "loaded_count": int(loaded or 0),
        "lazy_load": int(count or 0) > int(loaded or 0),
        "lazy_ctx": dict(lazy_ctx),
        "children": [],
    }


def _build_ipam_range_lazy_batch_node(ip_range, *, count, loaded):
    return _build_ipam_lazy_batch_node(
        ip_range,
        category="ip_addresses",
        count=count,
        loaded=loaded,
        stats=_ipam_range_stats(ip_range),
        lazy_ctx={"range_pk": ip_range.pk, "category": "ip_addresses"},
    )


def _build_ipam_range_resolve_nodes(ip_range, visited):
    """Expand an IPAM range to contained IP leaves (lazy when large)."""
    import netbox_nsm.analyzers.ip._lazy_api as _hub
    from netbox_nsm.analyzers.ip.addr_constants import FIELD_TYPE_LABELS

    ip_count = _ipam_range_ip_count(ip_range)
    limit = _IPAM_PREFIX_CHILDREN_MAX
    child_ips = (
        _collect_ipam_range_ip_children(ip_range) if ip_count <= limit else []
    )
    children = []
    for ip_obj in child_ips:
        ip_node = _hub._build_addr_tree_node(ip_obj, set(visited))
        if ip_node:
            children.append(ip_node)
    if ip_count > len(children):
        children.append(
            _build_ipam_range_lazy_batch_node(
                ip_range, count=ip_count, loaded=len(children)
            )
        )
    node = {
        "name": str(ip_range),
        "url": ip_range.get_absolute_url(),
        "kind": "group",
        "ip_ref": {
            "str": f"{ip_range.start_address} – {ip_range.end_address}",
            "url": ip_range.get_absolute_url(),
            "type": FIELD_TYPE_LABELS["range"],
        },
        "children": children,
    }
    return _attach_ipam_stats_meta(node, _ipam_range_stats(ip_range))


def _build_ipam_prefix_resolve_nodes(
    prefix, visited, *, grouped=None, stats=None, truncated=None
):
    """
    Recursively resolve a prefix to child prefixes, ranges (→ IPs), and IP leaves.

    No IPAM category wrappers — nested subnets recurse until IP leaves.
    """
    import netbox_nsm.analyzers.ip._lazy_api as _hub

    if grouped is None or stats is None or truncated is None:
        grouped, stats, truncated = _collect_ipam_prefix_children_impl(
            prefix, include_nsm_addresses=False
        )
    nodes = []

    prefix_count = int((stats.get("child_prefixes") or {}).get("count") or 0)
    child_prefixes = grouped.get("child_prefixes") or []
    for child_prefix in child_prefixes:
        child_node = _hub._build_addr_tree_node(
            child_prefix,
            _hub._addr_tree_child_visited(visited, child_prefix, prefix),
        )
        if child_node:
            nodes.append(child_node)
    if prefix_count > len(child_prefixes):
        nodes.append(
            _build_ipam_lazy_batch_node(
                prefix,
                category="child_prefixes",
                count=prefix_count,
                loaded=len(child_prefixes),
                stats=stats,
                lazy_ctx={"prefix_pk": prefix.pk, "category": "child_prefixes"},
            )
        )

    range_count = int((stats.get("ip_ranges") or {}).get("count") or 0)
    child_ranges = grouped.get("ip_ranges") or []
    for ip_range in child_ranges:
        range_node = _build_ipam_range_resolve_nodes(ip_range, visited)
        if range_node:
            nodes.append(range_node)
    if range_count > len(child_ranges):
        nodes.append(
            _build_ipam_lazy_batch_node(
                prefix,
                category="ip_ranges",
                count=range_count,
                loaded=len(child_ranges),
                stats=stats,
                lazy_ctx={"prefix_pk": prefix.pk, "category": "ip_ranges"},
            )
        )

    ip_count = int((stats.get("ip_addresses") or {}).get("count") or 0)
    child_ips = grouped.get("ip_addresses") or []
    for ip_obj in child_ips:
        ip_node = _hub._build_addr_tree_node(ip_obj, set(visited))
        if ip_node:
            nodes.append(ip_node)
    if ip_count > len(child_ips):
        nodes.append(
            _build_ipam_lazy_batch_node(
                prefix,
                category="ip_addresses",
                count=ip_count,
                loaded=len(child_ips),
                stats=stats,
                lazy_ctx={"prefix_pk": prefix.pk, "category": "ip_addresses"},
            )
        )

    return nodes


def _build_ipam_prefix_layer_node(prefix, visited):
    """
    Explicit IPAM prefix layer between an NSM address and resolved children.

    Tree shape: ``dm-addr`` (NSM) → ``10.x/24`` (this node) → child prefixes / ranges / IPs.
    """
    import netbox_nsm.analyzers.ip._lazy_api as _hub
    from django.contrib.contenttypes.models import ContentType
    from netbox_nsm.analyzers.ip.addr_constants import FIELD_TYPE_LABELS

    grouped, stats, truncated = _collect_ipam_prefix_children_impl(
        prefix, include_nsm_addresses=False
    )
    children = _build_ipam_prefix_resolve_nodes(
        prefix, visited, grouped=grouped, stats=stats, truncated=truncated
    )
    cidr = str(getattr(prefix, "prefix", prefix) or prefix)
    ct_id = ContentType.objects.get_for_model(prefix).pk
    node = {
        "name": cidr,
        "url": prefix.get_absolute_url(),
        "kind": "group",
        "layer": "ipam_prefix",
        "ip_ref": {
            "str": cidr,
            "url": prefix.get_absolute_url(),
            "type": FIELD_TYPE_LABELS["prefix"],
            "ct": str(ct_id),
            "pk": str(prefix.pk),
        },
        "children": children,
    }
    _attach_ipam_stats_meta(node, stats, truncated=truncated)
    return _hub._attach_addr_node_prefix_display(node, obj=prefix)


def _build_ipam_category_nodes(prefix, grouped, stats, visited):
    import netbox_nsm.analyzers.ip._lazy_api as _hub
    """Build first-level category groups under a prefix inventory node."""
    nodes = []
    order = ("child_prefixes", "ip_addresses", "ip_ranges", "nsm_addresses")
    large = _prefix_is_large(stats)
    for key in order:
        if key not in stats:
            continue
        stat = stats[key]
        count = int(stat.get("count") or 0)
        items = grouped.get(key) or []
        if large:
            cat_children = []
            loaded = 0
            lazy_load = count > 0
        else:
            cat_children = []
            for item in items:
                child = _hub._build_addr_tree_node(
                    item,
                    _hub._addr_tree_child_visited(visited, item, prefix),
                )
                if child:
                    cat_children.append(child)
            loaded = len(cat_children)
            lazy_load = count > loaded or bool(stat.get("truncated"))
        nodes.append(
            {
                "kind": "category",
                "name": stat["label"],
                "url": stat["url"],
                "count": count,
                "loaded_count": loaded,
                "lazy_load": lazy_load,
                "lazy_ctx": {
                    "prefix_pk": prefix.pk,
                    "category": key,
                },
                "children": cat_children,
            }
        )
    return nodes


def _collect_ipam_prefix_children(prefix):
    """Return analyzable children contained in or linked to an IPAM prefix."""
    grouped, _stats, _truncated = _collect_ipam_prefix_children_impl(
        prefix, include_nsm_addresses=True
    )
    return _flatten_ipam_grouped(grouped)


def _collect_ipam_prefix_ipam_children(prefix):
    """Prefix drill-down: child prefixes, IPs, and ranges only (no nsm_addresses)."""
    grouped, _stats, _truncated = _collect_ipam_prefix_children_impl(
        prefix, include_nsm_addresses=False
    )
    return _flatten_ipam_grouped(grouped)


def _collect_ipam_prefix_drilldown(prefix):
    """Drill-down from nsm_address FK with NetBox stats attached."""
    return _collect_ipam_prefix_children_impl(prefix, include_nsm_addresses=False)


def _is_ipam_addr_object(obj) -> bool:
    try:
        return (
            obj._meta.app_label == "ipam"
            and obj._meta.model_name in _IPAM_ADDR_MODEL_NAMES
        )
    except Exception:
        return False


def _collect_ipam_range_ip_children(ip_range):
    """IP range drill-down: contained IP addresses."""
    from ipam.models import IPAddress

    start = ip_range.start_address
    end = ip_range.end_address
    return list(
        IPAddress.objects.filter(address__gte=start, address__lte=end).order_by(
            "address"
        )[:_IPAM_PREFIX_CHILDREN_MAX]
    )


def _collect_ipam_drilldown_children(ipam_obj):
    """IPAM-only children for drill-down from nsm_address FK targets."""
    try:
        from ipam.models import IPRange, Prefix
    except ImportError:
        return []

    if isinstance(ipam_obj, Prefix):
        grouped, _stats, _truncated = _collect_ipam_prefix_drilldown(ipam_obj)
        return _flatten_ipam_grouped(grouped)
    if isinstance(ipam_obj, IPRange):
        return _collect_ipam_range_ip_children(ipam_obj)
    return []


