"""
Lazy-load child prefixes (subnets) for the Cell-Tree IP Analyzer table.

GET /plugins/netbox-nsm/api/ip-analyzer/subnet-children/?prefix_pk=&offset=
"""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views import View

from ._common import (
    mark_lazy_loaded_nodes,
    mark_lazy_subnet_child_nodes,
    parse_non_negative_int,
)
from netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils import (
    _prefix_ipam_stats,
    _query_ipam_category_objects,
)
from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import (
    _attach_ipa_dup_cell_statuses,
    _attach_ipa_dup_context_fields,
    _build_ipa_cell_object_tree,
    _mark_ipa_object_tree_duplicate_flags,
)
from netbox_nsm.analyzers.ip_analyzer.ipa_zone_label import (
    attach_ipa_cell_tenant_ref,
    attach_ipa_cell_zone_label_refs,
)

__all__ = ("IpAnalyzerSubnetChildrenApiView",)


def _build_lazy_subnet_nodes(child_prefixes, *, prefix_ct):
    """Build lazy subnet rows via the same cell-tree builder used during initial table render."""
    raw_selections = []
    obj_by_key = {}
    for obj in child_prefixes:
        key = (int(prefix_ct), int(obj.pk))
        obj_by_key[key] = obj
        raw_selections.append(
            {
                "ct": str(prefix_ct),
                "pk": str(obj.pk),
                "name": str(obj),
            }
        )
    return _build_ipa_cell_object_tree(raw_selections, obj_by_key)


def _mark_loaded_nodes_contained_in_parent(nodes, parent_prefix):
    """Ensure lazy child prefixes carry parent containment context for Dup semantics."""
    parent_cidr = str(getattr(parent_prefix, "prefix", "") or "")
    parent_name = str(parent_prefix)
    parent_url = (
        parent_prefix.get_absolute_url()
        if hasattr(parent_prefix, "get_absolute_url")
        else ""
    )
    for node in nodes or []:
        node.setdefault("subnet_contained_in", parent_cidr)
        node.setdefault("subnet_contained_in_name", parent_name)
        node.setdefault("subnet_contained_in_url", parent_url)
        node["subnet_contained_dup"] = True
        _mark_loaded_nodes_contained_in_parent(node.get("children") or [], parent_prefix)


class IpAnalyzerSubnetChildrenApiView(LoginRequiredMixin, View):
    """Load child prefixes (subnets) for Cell-Tree lazy expansion."""

    http_method_names = ["get"]

    def get(self, request):
        prefix_pk = request.GET.get("prefix_pk")
        offset_raw = request.GET.get("offset", "0")
        depth_raw = request.GET.get("depth", "0")

        offset = parse_non_negative_int(offset_raw, default=0)
        depth = parse_non_negative_int(depth_raw, default=0)

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

        prefix_ct = ContentType.objects.get_for_model(Prefix).pk
        nodes = _build_lazy_subnet_nodes(child_prefixes, prefix_ct=prefix_ct)
        mark_lazy_subnet_child_nodes(nodes)
        mark_lazy_loaded_nodes(nodes)
        # Re-attach refs after lazy flags so tenant/zone resolution does not get skipped.
        attach_ipa_cell_zone_label_refs(nodes, {})
        attach_ipa_cell_tenant_ref(nodes, {})
        _mark_loaded_nodes_contained_in_parent(nodes, prefix)
        _mark_ipa_object_tree_duplicate_flags(nodes, is_root=True)
        _attach_ipa_dup_cell_statuses(nodes)
        _attach_ipa_dup_context_fields(nodes)

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
                # Client sends parent row depth; children render one level deeper.
                "depth": depth + 1,
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
