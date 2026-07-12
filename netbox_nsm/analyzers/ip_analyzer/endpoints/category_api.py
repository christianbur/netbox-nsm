"""
Lazy-load prefix/range inventory for the IP Analyzer tree.

GET /plugins/netbox-nsm/api/ip-analyzer/category/?prefix_pk=&category=&offset=
GET /plugins/netbox-nsm/api/ip-analyzer/category/?range_pk=&offset=
"""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views import View

from netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils import (
    _build_addr_tree_node,
    _build_ipam_range_resolve_nodes,
    _enrich_addr_tree_copy_lines,
    _enrich_addr_tree_leaf_counts,
    _ipam_range_ip_count,
    _prefix_ipam_stats,
    _query_ipam_category_objects,
    _query_ipam_range_ip_objects,
)

__all__ = ("IpAnalyzerCategoryApiView",)

_VALID_CATEGORIES = frozenset(
    ("child_prefixes", "ip_addresses", "ip_ranges", "nsm_addresses")
)


def _build_category_drilldown_nodes(obj, category):
    """Build resolved tree nodes for one lazy-loaded inventory page."""
    if category == "ip_ranges":
        try:
            from ipam.models import IPRange
        except ImportError:
            return []
        if isinstance(obj, IPRange):
            node = _build_ipam_range_resolve_nodes(obj, set())
            return [node] if node else []
    node = _build_addr_tree_node(obj, set())
    return [node] if node else []


class IpAnalyzerCategoryApiView(LoginRequiredMixin, View):
    http_method_names = ["get"]

    def get(self, request):
        prefix_pk = request.GET.get("prefix_pk")
        range_pk = request.GET.get("range_pk")
        category = request.GET.get("category")
        render_prefix = "ipa" if request.GET.get("prefix") == "ipa" else "lazy"
        depth_raw = request.GET.get("depth", "2")
        offset_raw = request.GET.get("offset", "0")

        try:
            depth = max(int(depth_raw), 0)
        except (TypeError, ValueError):
            depth = 2

        try:
            offset = max(int(offset_raw), 0)
        except (TypeError, ValueError):
            offset = 0

        if str(range_pk).isdigit():
            from ipam.models import IPRange

            ip_range = IPRange.objects.filter(pk=int(range_pk)).first()
            if ip_range is None:
                return JsonResponse({"error": "range not found"}, status=404)

            objs = _query_ipam_range_ip_objects(ip_range, offset=offset)
            total = _ipam_range_ip_count(ip_range)
            nodes = []
            for obj in objs:
                node = _build_addr_tree_node(obj, set())
                if node:
                    _enrich_addr_tree_copy_lines(node)
                    _enrich_addr_tree_leaf_counts(node)
                    nodes.append(node)
            loaded = offset + len(nodes)
            html = render_to_string(
                "netbox_nsm/inc/addr_tree_nodes_fragment.html",
                {
                    "nodes": nodes,
                    "depth": depth,
                    "prefix": render_prefix,
                    "show_copy": True,
                    "ipa_cell_pill": False,
                },
                request=request,
            )
            return JsonResponse(
                {
                    "html": html,
                    "loaded": loaded,
                    "total": total,
                    "has_more": loaded < total,
                }
            )

        if not (str(prefix_pk).isdigit() and category in _VALID_CATEGORIES):
            return JsonResponse(
                {"error": "prefix_pk and category, or range_pk required"},
                status=400,
            )

        from ipam.models import Prefix

        prefix = Prefix.objects.filter(pk=int(prefix_pk)).first()
        if prefix is None:
            return JsonResponse({"error": "prefix not found"}, status=404)

        objs = _query_ipam_category_objects(prefix, category, offset=offset)
        nodes = []
        for obj in objs:
            for node in _build_category_drilldown_nodes(obj, category):
                _enrich_addr_tree_copy_lines(node)
                _enrich_addr_tree_leaf_counts(node)
                nodes.append(node)

        stats = _prefix_ipam_stats(prefix)
        stat = stats.get(category) or {}
        total = int(stat.get("count") or 0)
        loaded = offset + len(objs)

        html = render_to_string(
            "netbox_nsm/inc/addr_tree_nodes_fragment.html",
            {
                "nodes": nodes,
                "depth": depth,
                "prefix": render_prefix,
                "show_copy": True,
                "ipa_cell_pill": False,
            },
            request=request,
        )
        return JsonResponse(
            {
                "html": html,
                "loaded": loaded,
                "total": total,
                "has_more": loaded < total,
            }
        )
