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

__all__ = ("AnalyzerAPIView",)


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
        from netbox_nsm.analyzer import registry, node_from_object

        root_node = node_from_object(obj)
        edges = registry.get_edges(obj)

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
