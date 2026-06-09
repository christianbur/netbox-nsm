"""
Lazy-load prefix inventory categories for the IP Analyzer tree.

GET /plugins/netbox-nsm/api/ip-analysis/category/?prefix_pk=&category=&offset=
"""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views import View

from netbox_nsm.analysis.addr_analysis_utils import (
    _build_addr_tree_node,
    _enrich_addr_tree_copy_lines,
    _enrich_addr_tree_leaf_counts,
    _prefix_ipam_stats,
    _query_ipam_category_objects,
)

__all__ = ("IpAnalysisCategoryApiView",)

_VALID_CATEGORIES = frozenset(
    ("child_prefixes", "ip_addresses", "ip_ranges", "nsm_addresses")
)


class IpAnalysisCategoryApiView(LoginRequiredMixin, View):
    http_method_names = ["get"]

    def get(self, request):
        prefix_pk = request.GET.get("prefix_pk")
        category = request.GET.get("category")
        offset_raw = request.GET.get("offset", "0")

        if not (str(prefix_pk).isdigit() and category in _VALID_CATEGORIES):
            return JsonResponse({"error": "prefix_pk and category required"}, status=400)

        try:
            offset = max(int(offset_raw), 0)
        except (TypeError, ValueError):
            offset = 0

        from ipam.models import Prefix

        prefix = Prefix.objects.filter(pk=int(prefix_pk)).first()
        if prefix is None:
            return JsonResponse({"error": "prefix not found"}, status=404)

        objs = _query_ipam_category_objects(prefix, category, offset=offset)
        nodes = []
        for obj in objs:
            node = _build_addr_tree_node(obj, set())
            if node:
                _enrich_addr_tree_copy_lines(node)
                _enrich_addr_tree_leaf_counts(node)
                nodes.append(node)

        stats = _prefix_ipam_stats(prefix)
        stat = stats.get(category) or {}
        total = int(stat.get("count") or 0)
        loaded = offset + len(nodes)

        html = render_to_string(
            "netbox_nsm/inc/addr_tree_nodes_fragment.html",
            {"nodes": nodes, "depth": 2, "prefix": "lazy", "show_copy": True},
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
