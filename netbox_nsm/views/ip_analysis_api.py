"""
JSON API for the floating IP Analyzer applet.

GET /plugins/netbox-nsm/api/ip-analysis/?ct=<id>&pk=<id>&ct=...&pk=...
"""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views import View

from netbox_nsm.views.rulebook import (
    _build_multi_object_addr_analysis,
    _leaf_count_for_addr_analysis,
    _object_is_addr_analyzable,
)

__all__ = ("IpAnalysisApiView",)


class IpAnalysisApiView(LoginRequiredMixin, View):
    http_method_names = ["get"]

    def get(self, request):
        ct_list = request.GET.getlist("ct")
        pk_list = request.GET.getlist("pk")

        if not ct_list or not pk_list:
            return JsonResponse({"error": "ct and pk required"}, status=400)

        selections = []
        objs = []
        seen: set[tuple[int, int]] = set()
        unsupported = []

        for i, ct_str in enumerate(ct_list):
            pk_str = pk_list[i] if i < len(pk_list) else ""
            if not (str(ct_str).isdigit() and str(pk_str).isdigit()):
                continue
            key = (int(ct_str), int(pk_str))
            if key in seen:
                continue
            try:
                ct = ContentType.objects.get(pk=key[0])
                mc = ct.model_class()
                if not mc:
                    continue
                obj = mc.objects.filter(pk=key[1]).first()
                if not obj:
                    continue
                seen.add(key)
                name = getattr(obj, "name", None) or str(obj)
                if not _object_is_addr_analyzable(obj, key[0]):
                    unsupported.append(
                        {"ct": str(key[0]), "pk": str(key[1]), "name": str(name)}
                    )
                    continue
                selections.append(
                    {"ct": str(key[0]), "pk": str(key[1]), "name": str(name)}
                )
                objs.append(obj)
            except Exception:
                continue

        if not objs:
            return JsonResponse(
                {
                    "html": "",
                    "leaf_count": 0,
                    "objects": selections,
                    "unsupported": unsupported,
                    "message": (
                        "Keine analysierbaren Adressobjekte."
                        if unsupported
                        else "Keine gültigen Objekte ausgewählt."
                    ),
                }
            )

        addr_analysis = _build_multi_object_addr_analysis(objs)
        leaf_count = _leaf_count_for_addr_analysis(addr_analysis)
        if leaf_count == 0:
            return JsonResponse(
                {
                    "html": "",
                    "leaf_count": 0,
                    "objects": selections,
                    "unsupported": unsupported,
                    "message": "Keine IP-Adressen aufgelöst.",
                }
            )

        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": addr_analysis},
            request=request,
        )
        return JsonResponse(
            {
                "html": html,
                "leaf_count": leaf_count,
                "objects": selections,
                "unsupported": unsupported,
            }
        )
