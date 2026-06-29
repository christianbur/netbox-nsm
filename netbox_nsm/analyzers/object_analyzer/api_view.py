"""
JSON API view for the Object Analyzer.
GET /plugins/netbox-nsm/api/analyzer/?ct=<ct_id>&pk=<pk>
"""

from __future__ import annotations

import dataclasses
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.views import View

__all__ = ("AnalyzerAPIView", "AnalyzerPickerAPIView")


class AnalyzerPickerAPIView(LoginRequiredMixin, View):
    """Batched link tree for the Object Analyzer "+" link picker.

    GET /plugins/netbox-nsm/api/analyzer/picker/?ct=<ct_id>&pk=<pk>&depth=<1|2>&mode=<all|security>

    Returns the clicked node's direct links (L1) and, for ``depth=2`` (default),
    each L1 child's links (L2) in a single response — replacing the previous
    ``1 + N`` per-child request storm.
    """

    http_method_names = ["get"]

    def get(self, request):
        ct_str = request.GET.get("ct", "")
        pk_str = request.GET.get("pk", "")
        depth_str = request.GET.get("depth", "2")

        if not (ct_str.isdigit() and pk_str.isdigit()):
            return JsonResponse({"error": "ct and pk required"}, status=400)

        depth = 2 if depth_str not in ("1", "2") else int(depth_str)
        mode = request.GET.get("mode", "all")

        try:
            ct = ContentType.objects.get_for_id(int(ct_str))
            mc = ct.model_class()
            if not mc:
                raise ValueError("no model class")
            obj = mc.objects.get(pk=int(pk_str))
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=404)

        from netbox_nsm.analyzers.object_analyzer.picker import build_picker_tree

        return JsonResponse(build_picker_tree(obj, depth=depth, mode=mode))


class AnalyzerAPIView(LoginRequiredMixin, View):
    http_method_names = ["get"]

    def get(self, request):
        ct_str = request.GET.get("ct", "")
        pk_str = request.GET.get("pk", "")

        if not (ct_str.isdigit() and pk_str.isdigit()):
            return JsonResponse({"error": "ct and pk required"}, status=400)

        try:
            ct = ContentType.objects.get(pk=int(ct_str))
            mc = ct.model_class()
            if not mc:
                raise ValueError("no model class")
            obj = mc.objects.get(pk=int(pk_str))
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=404)

        # Import here to ensure relations are registered
        from netbox_nsm.analyzers.object_analyzer import node_from_object
        from netbox_nsm.analyzers.object_analyzer.modes import get_filtered_edges, parse_analyzer_mode

        mode = parse_analyzer_mode(request.GET.get("mode", "all"))
        root_node = node_from_object(obj)
        edges = get_filtered_edges(obj, mode)

        return JsonResponse(
            {
                "node": dataclasses.asdict(root_node),
                "children": [
                    {
                        "edge_label": e.edge_label,
                        "edge_type": e.edge_type,
                        "node": dataclasses.asdict(e.node),
                    }
                    for e in edges
                ],
            }
        )
