"""Shared IP Analysis payload building for UI and REST APIs."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

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

__all__ = (
    "build_ip_analysis_payload",
    "execute_ip_analysis_diff",
    "execute_ip_analysis_merge",
    "parse_diff_sides_from_body",
    "parse_diff_sides_from_request",
    "parse_object_refs",
    "parse_selections_from_request",
)


def _object_ref_key(ref: dict) -> tuple[int, int] | None:
    ct_raw = ref.get("content_type", ref.get("content_type_id", ref.get("ct")))
    pk_raw = ref.get("id", ref.get("object_id", ref.get("pk")))
    if ct_raw is None or pk_raw is None:
        return None
    if not (str(ct_raw).isdigit() and str(pk_raw).isdigit()):
        return None
    return int(ct_raw), int(pk_raw)


def parse_object_refs(refs):
    """
    Resolve a list of object references into selections and ORM objects.

    Each ref accepts ``content_type``/``ct`` and ``id``/``pk`` keys.
    """
    selections = []
    raw_selections = []
    objs = []
    obj_by_key: dict[tuple[int, int], object] = {}
    unsupported = []
    seen: set[tuple[int, int]] = set()

    for ref in refs or []:
        if not isinstance(ref, dict):
            continue
        key = _object_ref_key(ref)
        if key is None:
            continue
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


def _parse_object_lists(ct_list, pk_list):
    refs = []
    for i, ct_str in enumerate(ct_list or []):
        pk_str = pk_list[i] if i < len(pk_list) else ""
        refs.append({"ct": ct_str, "pk": pk_str})
    return parse_object_refs(refs)


def parse_selections_from_request(request, *, prefix=""):
    ct_list = request.GET.getlist(f"{prefix}ct")
    pk_list = request.GET.getlist(f"{prefix}pk")
    return _parse_object_lists(ct_list, pk_list)


def parse_diff_sides_from_request(request):
    sides = []
    index = 0
    while True:
        prefix = f"s{index}_"
        ct_list = request.GET.getlist(f"{prefix}ct")
        if not ct_list:
            break
        pk_list = request.GET.getlist(f"{prefix}pk")
        label = (request.GET.get(f"{prefix}name") or "").strip() or chr(65 + index)
        selections, objs, unsupported, _, _ = _parse_object_lists(ct_list, pk_list)
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

    selections_a, objs_a, unsupported_a, _, _ = parse_selections_from_request(
        request, prefix="a_"
    )
    selections_b, objs_b, unsupported_b, _, _ = parse_selections_from_request(
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


def _objects_from_side_spec(side_spec):
    refs = side_spec.get("objects") or side_spec.get("object_refs") or []
    return parse_object_refs(refs)


def parse_diff_sides_from_body(body):
    """Parse diff sides from a JSON request body."""
    if not isinstance(body, dict):
        return []

    sides_payload = body.get("sides")
    if isinstance(sides_payload, list) and len(sides_payload) >= 2:
        sides = []
        for index, side_spec in enumerate(sides_payload):
            if not isinstance(side_spec, dict):
                continue
            label = (side_spec.get("label") or "").strip() or chr(65 + index)
            selections, objs, unsupported, _, _ = _objects_from_side_spec(side_spec)
            sides.append(
                {
                    "label": label,
                    "selections": selections,
                    "objs": objs,
                    "unsupported": unsupported,
                }
            )
        return sides

    side_a = body.get("side_a") or body.get("a")
    side_b = body.get("side_b") or body.get("b")
    if isinstance(side_a, dict) and isinstance(side_b, dict):
        sides = []
        for index, side_spec in enumerate((side_a, side_b)):
            label = (side_spec.get("label") or "").strip() or ("A" if index == 0 else "B")
            selections, objs, unsupported, _, _ = _objects_from_side_spec(side_spec)
            sides.append(
                {
                    "label": label,
                    "selections": selections,
                    "objs": objs,
                    "unsupported": unsupported,
                }
            )
        return sides

    return []


def build_ip_analysis_payload(
    *,
    addr_analysis,
    selections,
    unsupported,
    mode="merge",
    diff_summary=None,
    raw_selections=None,
    obj_by_key=None,
    request=None,
    include_html=False,
    include_structured_data=True,
):
    """Build a JSON-serializable analysis payload; optionally include rendered HTML."""
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

    payload = {
        "mode": mode,
        "leaf_count": leaf_count,
        "count_subnets": type_counts.get("count_subnets") or 0,
        "count_ranges": type_counts.get("count_ranges") or 0,
        "count_ips": type_counts.get("count_ips") or 0,
        "count_duplicates": type_counts.get("count_duplicates") or 0,
        "objects": selections,
        "unsupported": unsupported,
    }
    if include_structured_data:
        payload["addr_analysis"] = addr_analysis or []
        payload["object_tree"] = object_tree or None
    if diff_summary is not None:
        payload["diff_summary"] = diff_summary

    if leaf_count == 0 and not object_tree:
        payload["message"] = _("No IP addresses resolved.")
        if include_html:
            payload["html"] = ""
        return payload

    if include_html and request is not None:
        payload["html"] = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {
                "addr_analysis": addr_analysis,
                "object_tree": object_tree or None,
                "summary_type_counts": type_counts,
            },
            request=request,
        )
    return payload


def execute_ip_analysis_merge(
    *,
    selections,
    objs,
    unsupported,
    raw_selections,
    obj_by_key,
    request=None,
    include_html=False,
    include_structured_data=True,
):
    if not objs and not raw_selections:
        payload = {
            "mode": "merge",
            "html": "" if include_html else None,
            "leaf_count": 0,
            "count_subnets": 0,
            "count_ranges": 0,
            "count_ips": 0,
            "count_duplicates": 0,
            "objects": selections,
            "unsupported": unsupported,
            "message": (
                _("No analyzable address objects.")
                if unsupported
                else _("No valid objects selected.")
            ),
        }
        if include_structured_data:
            payload["addr_analysis"] = []
            payload["object_tree"] = None
        if not include_html:
            payload.pop("html", None)
        return payload

    if not objs:
        payload = {
            "mode": "merge",
            "html": "" if include_html else None,
            "leaf_count": 0,
            "count_subnets": 0,
            "count_ranges": 0,
            "count_ips": 0,
            "count_duplicates": 0,
            "objects": selections,
            "unsupported": unsupported,
            "message": (
                _("No analyzable address objects.")
                if unsupported
                else _("No IP addresses resolved.")
            ),
        }
        if include_structured_data:
            payload["addr_analysis"] = []
            payload["object_tree"] = None
        if not include_html:
            payload.pop("html", None)
        return payload

    addr_analysis = _build_multi_object_addr_analysis(objs)
    payload = build_ip_analysis_payload(
        addr_analysis=addr_analysis,
        selections=selections,
        unsupported=unsupported,
        mode="merge",
        raw_selections=raw_selections,
        obj_by_key=obj_by_key,
        request=request,
        include_html=include_html,
        include_structured_data=include_structured_data,
    )
    if include_html and "html" not in payload:
        payload["html"] = ""
    elif not include_html:
        payload.pop("html", None)
    return payload


def execute_ip_analysis_diff(
    *, sides, request=None, include_html=False, include_structured_data=True
):
    unsupported = []
    selections = []
    for side in sides:
        unsupported.extend(side.get("unsupported") or [])
        selections.extend(side.get("selections") or [])

    has_objs = any(side.get("objs") for side in sides)
    if not has_objs:
        payload = {
            "mode": "diff",
            "html": "" if include_html else None,
            "leaf_count": 0,
            "count_subnets": 0,
            "count_ranges": 0,
            "count_ips": 0,
            "count_duplicates": 0,
            "objects": selections,
            "unsupported": unsupported,
            "message": (
                _("No analyzable address objects.")
                if unsupported
                else _("No valid objects selected for diff.")
            ),
        }
        if include_structured_data:
            payload["addr_analysis"] = []
            payload["object_tree"] = None
        if not include_html:
            payload.pop("html", None)
        return payload

    addr_analysis = _build_addr_diff_analysis_from_sides(
        [{"objs": side["objs"], "label": side["label"]} for side in sides]
    )
    diff_summary = None
    if addr_analysis:
        type_block = (addr_analysis[0].get("types") or [{}])[0]
        diff_summary = type_block.get("diff_summary")

    payload = build_ip_analysis_payload(
        addr_analysis=addr_analysis,
        selections=selections,
        unsupported=unsupported,
        mode="diff",
        diff_summary=diff_summary,
        request=request,
        include_html=include_html,
        include_structured_data=include_structured_data,
    )
    if include_html and "html" not in payload:
        payload["html"] = ""
    elif not include_html:
        payload.pop("html", None)
    return payload


def ip_analysis_json_response(payload, *, status=200):
    clean = {key: value for key, value in payload.items() if value is not None}
    return JsonResponse(clean, status=status)
