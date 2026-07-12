"""
Lazy-load child prefixes (subnets) for the Cell-Tree IP Analyzer table.

GET /plugins/netbox-nsm/api/ip-analyzer/subnet-children/?prefix_pk=&offset=
"""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views import View

from netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils import (
    _build_addr_tree_node,
    _enrich_addr_tree_copy_lines,
    _enrich_addr_tree_leaf_counts,
    _prefix_ipam_stats,
    _query_ipam_category_objects,
)

__all__ = ("IpAnalyzerSubnetChildrenApiView",)


def _mark_lazy_loaded_nodes(nodes):
    for node in nodes or []:
        node["ipa_lazy_loaded"] = True
        _mark_lazy_loaded_nodes(node.get("children") or [])


class IpAnalyzerSubnetChildrenApiView(LoginRequiredMixin, View):
    """Load child prefixes (subnets) for Cell-Tree lazy expansion."""

    http_method_names = ["get"]

    def get(self, request):
        prefix_pk = request.GET.get("prefix_pk")
        offset_raw = request.GET.get("offset", "0")

        try:
            offset = max(int(offset_raw), 0)
        except (TypeError, ValueError):
            offset = 0

        if not str(prefix_pk).isdigit():
            return JsonResponse(
                {"error": "prefix_pk required"},
                status=400,
            )

        from ipam.models import Prefix

        prefix = Prefix.objects.filter(pk=int(prefix_pk)).first()
        if prefix is None:
            return JsonResponse({"error": "prefix not found"}, status=404)

        # Query child prefixes only (subnets)
        child_prefixes = _query_ipam_category_objects(
            prefix, "child_prefixes", offset=offset
        )
        
        nodes = []
        for obj in child_prefixes:
            node = _build_addr_tree_node(obj, set())
            if node:
                _enrich_addr_tree_copy_lines(node)
                _enrich_addr_tree_leaf_counts(node)
                node["ipa_lazy_subnet_child"] = True
                node["ipa_lazy_loaded"] = True
                nodes.append(node)

        _mark_lazy_loaded_nodes(nodes)

        # Get stats for total count
        stats = _prefix_ipam_stats(prefix)
        stat = stats.get("child_prefixes") or {}
        total = int(stat.get("count") or 0)
        loaded = offset + len(child_prefixes)

        # Render as Cell-Tree rows
        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_subnet_children_fragment.html",
            {
                "nodes": nodes,
                "depth": 1,  # Child prefixes have same depth as parent in cell-tree
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
