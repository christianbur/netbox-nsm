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

from netbox_nsm.analysis.addr_analysis_utils import (
    _apply_object_tree_copy_lines,
    _apply_summary_type_counts_to_addr_analysis,
    _build_addr_diff_analysis_from_sides,
    _build_ipa_cell_object_tree,
    _build_multi_object_addr_analysis,
    _ipa_cell_object_tree_visible,
    _leaf_count_for_addr_analysis,
    _object_is_addr_analyzable,
    _resolve_summary_type_counts,
)

__all__ = ("IpAnalysisApiView",)


def _parse_ip_analysis_selections(request, *, prefix=""):
    """Parse repeated ct/pk pairs; optional prefix e.g. 'a_' for diff side A."""
    ct_list = request.GET.getlist(f"{prefix}ct")
    pk_list = request.GET.getlist(f"{prefix}pk")

    selections = []
    raw_selections = []
    objs = []
    obj_by_key: dict[tuple[int, int], object] = {}
    seen: set[tuple[int, int]] = set()
    unsupported = []

    for i, ct_str in enumerate(ct_list):
        pk_str = pk_list[i] if i < len(pk_list) else ""
        if not (str(ct_str).isdigit() and str(pk_str).isdigit()):
            continue
        key = (int(ct_str), int(pk_str))
        try:
            ct = ContentType.objects.get(pk=key[0])
            mc = ct.model_class()
            if not mc:
                continue
            obj = mc.objects.filter(pk=key[1]).first()
            if not obj:
                continue
            name = getattr(obj, "name", None) or str(obj)
            raw_selections.append(
                {"ct": str(key[0]), "pk": str(key[1]), "name": str(name)}
            )
            obj_by_key[key] = obj
            if key in seen:
                continue
            seen.add(key)
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

    return selections, objs, unsupported, raw_selections, obj_by_key


def _parse_ip_analysis_object_lists(ct_list, pk_list):
    """Parse parallel ct/pk lists into selections and resolved objects."""
    selections = []
    objs = []
    unsupported = []
    seen: set[tuple[int, int]] = set()

    for i, ct_str in enumerate(ct_list):
        pk_str = pk_list[i] if i < len(pk_list) else ""
        if not (str(ct_str).isdigit() and str(pk_str).isdigit()):
            continue
        key = (int(ct_str), int(pk_str))
        try:
            ct = ContentType.objects.get(pk=key[0])
            mc = ct.model_class()
            if not mc:
                continue
            obj = mc.objects.filter(pk=key[1]).first()
            if not obj:
                continue
            name = getattr(obj, "name", None) or str(obj)
            if key in seen:
                continue
            seen.add(key)
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

    return selections, objs, unsupported


def _parse_diff_sides(request):
    """
    Parse N diff sides from indexed s{i}_ct/s{i}_pk params (N >= 2),
    or legacy a_/b_ params for two-tab diffs.
    """
    sides = []
    index = 0
    while True:
        prefix = f"s{index}_"
        ct_list = request.GET.getlist(f"{prefix}ct")
        if not ct_list:
            break
        pk_list = request.GET.getlist(f"{prefix}pk")
        label = (request.GET.get(f"{prefix}name") or "").strip() or chr(65 + index)
        selections, objs, unsupported = _parse_ip_analysis_object_lists(
            ct_list, pk_list
        )
        sides.append(
            {
                "label": label,
                "selections": selections,
                "objs": objs,
                "unsupported": unsupported,
            }
        )
        index += 1

    if len(sides) >= 2:
        return sides

    selections_a, objs_a, unsupported_a, _, _ = _parse_ip_analysis_selections(
        request, prefix="a_"
    )
    selections_b, objs_b, unsupported_b, _, _ = _parse_ip_analysis_selections(
        request, prefix="b_"
    )
    if selections_a or selections_b or objs_a or objs_b:
        return [
            {
                "label": (request.GET.get("a_name") or "").strip() or "A",
                "selections": selections_a,
                "objs": objs_a,
                "unsupported": unsupported_a,
            },
            {
                "label": (request.GET.get("b_name") or "").strip() or "B",
                "selections": selections_b,
                "objs": objs_b,
                "unsupported": unsupported_b,
            },
        ]
    return sides


def _render_ip_analysis_response(
    request,
    *,
    addr_analysis,
    selections,
    unsupported,
    mode="merge",
    diff_summary=None,
    raw_selections=None,
    obj_by_key=None,
):
    leaf_count = _leaf_count_for_addr_analysis(addr_analysis)

    object_tree = []
    if mode != "diff" and raw_selections and obj_by_key:
        object_tree = _build_ipa_cell_object_tree(raw_selections, obj_by_key)
        if not _ipa_cell_object_tree_visible(object_tree, len(raw_selections)):
            object_tree = []

    if object_tree:
        addr_analysis = _apply_object_tree_copy_lines(addr_analysis, object_tree)

    type_counts = _resolve_summary_type_counts(addr_analysis, object_tree)
    if addr_analysis:
        _apply_summary_type_counts_to_addr_analysis(addr_analysis, type_counts)

    if leaf_count == 0 and not object_tree:
        return JsonResponse(
            {
                "html": "",
                "leaf_count": 0,
                "count_subnets": 0,
                "count_ranges": 0,
                "count_ips": 0,
                "objects": selections,
                "unsupported": unsupported,
                "mode": mode,
                "diff_summary": diff_summary,
                "message": "Keine IP-Adressen aufgelöst.",
            }
        )

    html = render_to_string(
        "netbox_nsm/inc/addr_analysis_applet_body.html",
        {
            "addr_analysis": addr_analysis,
            "object_tree": object_tree or None,
            "summary_type_counts": type_counts,
        },
        request=request,
    )
    payload = {
        "html": html,
        "leaf_count": leaf_count,
        "count_subnets": type_counts["count_subnets"],
        "count_ranges": type_counts["count_ranges"],
        "count_ips": type_counts["count_ips"],
        "count_duplicates": type_counts.get("count_duplicates") or 0,
        "objects": selections,
        "unsupported": unsupported,
        "mode": mode,
    }
    if diff_summary is not None:
        payload["diff_summary"] = diff_summary
    return JsonResponse(payload)


class IpAnalysisApiView(LoginRequiredMixin, View):
    http_method_names = ["get"]

    def get(self, request):
        mode = (request.GET.get("mode") or "merge").strip().lower()

        if mode == "diff":
            return self._get_diff(request)

        ct_list = request.GET.getlist("ct")
        pk_list = request.GET.getlist("pk")

        if not ct_list or not pk_list:
            return JsonResponse({"error": "ct and pk required"}, status=400)

        selections, objs, unsupported, raw_selections, obj_by_key = (
            _parse_ip_analysis_selections(request)
        )

        if not objs and not raw_selections:
            return JsonResponse(
                {
                    "html": "",
                    "leaf_count": 0,
                    "objects": selections,
                    "unsupported": unsupported,
                    "mode": "merge",
                    "message": (
                        "Keine analysierbaren Adressobjekte."
                        if unsupported
                        else "Keine gültigen Objekte ausgewählt."
                    ),
                }
            )

        if not objs:
            return JsonResponse(
                {
                    "html": "",
                    "leaf_count": 0,
                    "objects": selections,
                    "unsupported": unsupported,
                    "mode": "merge",
                    "message": (
                        "Keine analysierbaren Adressobjekte."
                        if unsupported
                        else "Keine IP-Adressen aufgelöst."
                    ),
                }
            )

        addr_analysis = _build_multi_object_addr_analysis(objs)
        return _render_ip_analysis_response(
            request,
            addr_analysis=addr_analysis,
            selections=selections,
            unsupported=unsupported,
            mode="merge",
            raw_selections=raw_selections,
            obj_by_key=obj_by_key,
        )

    def _get_diff(self, request):
        sides = _parse_diff_sides(request)
        if len(sides) < 2:
            return JsonResponse(
                {"error": "At least two diff sides required"}, status=400
            )

        unsupported = []
        selections = []
        for side in sides:
            unsupported.extend(side["unsupported"])
            selections.extend(side["selections"])

        has_objs = any(side["objs"] for side in sides)
        if not has_objs:
            return JsonResponse(
                {
                    "html": "",
                    "leaf_count": 0,
                    "objects": selections,
                    "unsupported": unsupported,
                    "mode": "diff",
                    "message": (
                        "Keine analysierbaren Adressobjekte."
                        if unsupported
                        else "Keine gültigen Objekte für den Diff ausgewählt."
                    ),
                }
            )

        addr_analysis = _build_addr_diff_analysis_from_sides(
            [{"objs": side["objs"], "label": side["label"]} for side in sides]
        )
        diff_summary = None
        if addr_analysis:
            type_block = (addr_analysis[0].get("types") or [{}])[0]
            diff_summary = type_block.get("diff_summary")

        return _render_ip_analysis_response(
            request,
            addr_analysis=addr_analysis,
            selections=selections,
            unsupported=unsupported,
            mode="diff",
            diff_summary=diff_summary,
        )
