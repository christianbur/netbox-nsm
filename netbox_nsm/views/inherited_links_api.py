from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse, HttpResponseBadRequest
from django.views import View

from netbox_nsm.ipam_inheritance import (
    ancestor_prefixes_for_ipam,
    nsm_address_q_for_ancestor,
)
from netbox_nsm.models import ObjectLink

__all__ = ("InheritedLinksApiView",)


class InheritedLinksApiView(View):
    """
    JSON endpoint that returns ObjectLinks inherited from containing Prefixes
    for an IPAM object (IPAddress, IPRange, or Prefix).

    GET /plugins/netbox-nsm/api/inherited-links/
        ?ct_id=<int>&obj_id=<int>
    """

    def get(self, request):
        try:
            ct_id = int(request.GET["ct_id"])
            obj_id = int(request.GET["obj_id"])
        except (KeyError, ValueError):
            return HttpResponseBadRequest("ct_id and obj_id are required integers")

        try:
            ct = ContentType.objects.get(pk=ct_id)
        except ContentType.DoesNotExist:
            return HttpResponseBadRequest("Invalid ct_id")

        model = ct.model_class()
        if model is None:
            return JsonResponse({"groups": [], "total": 0})

        try:
            obj = model.objects.get(pk=obj_id)
        except model.DoesNotExist:
            return HttpResponseBadRequest("Object not found")

        try:
            from ipam.models import Prefix, IPAddress, IPRange
            from netbox_nsm.models import TypeConfig as _TypeConfig
            from netbox_nsm.display_utils import (
                get_display_template_map,
                render_object_display,
                tc_panel_label,
            )
            from django.db.models import prefetch_related_objects

            if not isinstance(obj, (IPAddress, IPRange, Prefix)):
                return JsonResponse({"groups": [], "total": 0})

            tc_map = {
                tc.content_type_id: tc
                for tc in _TypeConfig.objects.select_related("content_type").all()
            }
            tmpl_map = get_display_template_map()

            ancestor_prefixes = ancestor_prefixes_for_ipam(obj)
            if not ancestor_prefixes:
                return JsonResponse({"groups": [], "total": 0})

            direct_fwd = list(
                ObjectLink.objects.filter(
                    object_a_type=ct, object_a_id=obj_id
                ).select_related("object_b_type")
            )
            direct_rev = list(
                ObjectLink.objects.filter(
                    object_b_type=ct, object_b_id=obj_id
                ).select_related("object_a_type")
            )
            covered_type_keys: set = set()
            for link in direct_fwd:
                lct = link.object_b_type
                covered_type_keys.add(f"{lct.app_label}__{lct.model}")
            for link in direct_rev:
                lct = link.object_a_type
                covered_type_keys.add(f"{lct.app_label}__{lct.model}")

            prefix_ct = ContentType.objects.get_for_model(Prefix)
            inh_links_by_type: dict = {}
            seen_link_urls: set = set()

            def _append_inherited(type_key, lct, linked, ancestor, tc):
                if tc is None or not tc.inherit_links:
                    return
                if tc.inherit_stop_on_own and type_key in covered_type_keys:
                    return
                obj_url = (
                    linked.get_absolute_url()
                    if hasattr(linked, "get_absolute_url")
                    else "#"
                )
                dedupe_key = (type_key, obj_url)
                if dedupe_key in seen_link_urls:
                    return
                seen_link_urls.add(dedupe_key)
                if type_key not in inh_links_by_type:
                    inh_links_by_type[type_key] = {
                        "label": tc_panel_label(lct, tc),
                        "objects": [],
                    }
                    covered_type_keys.add(type_key)
                inh_links_by_type[type_key]["objects"].append(
                    {
                        "url": obj_url,
                        "name": render_object_display(linked, lct.pk, tmpl_map),
                        "inherited_from_url": ancestor.get_absolute_url(),
                        "inherited_from_name": str(ancestor),
                    }
                )

            for ancestor in ancestor_prefixes:
                for direction in ("fwd", "rev"):
                    if direction == "fwd":
                        qs_inh = list(
                            ObjectLink.objects.filter(
                                object_a_type=prefix_ct, object_a_id=ancestor.pk
                            ).select_related("object_b_type")
                        )
                        prefetch_related_objects(qs_inh, "object_b")
                    else:
                        qs_inh = list(
                            ObjectLink.objects.filter(
                                object_b_type=prefix_ct, object_b_id=ancestor.pk
                            ).select_related("object_a_type")
                        )
                        prefetch_related_objects(qs_inh, "object_a")

                    for link in qs_inh:
                        linked = link.object_b if direction == "fwd" else link.object_a
                        if linked is None:
                            continue
                        lct = (
                            link.object_b_type
                            if direction == "fwd"
                            else link.object_a_type
                        )
                        type_key = f"{lct.app_label}__{lct.model}"
                        tc = tc_map.get(lct.pk)
                        _append_inherited(type_key, lct, linked, ancestor, tc)

            seen_addr_pks: set = set()
            try:
                from netbox_custom_objects.models import CustomObjectType as _COT

                _addr_cot = _COT.objects.filter(slug="nsm_addresses").first()
                if _addr_cot:
                    _AddrModel = _addr_cot.get_model()
                    _addr_ct = ContentType.objects.get_for_model(_AddrModel)
                    _addr_type_key = f"{_addr_ct.app_label}__{_addr_ct.model}"
                    tc = tc_map.get(_addr_ct.pk)
                    if tc and tc.inherit_links:
                        if not (
                            tc.inherit_stop_on_own
                            and _addr_type_key in covered_type_keys
                        ):
                            for ancestor in ancestor_prefixes:
                                for _addr_obj in nsm_address_q_for_ancestor(
                                    _AddrModel, ancestor, obj
                                ):
                                    if _addr_obj.pk in seen_addr_pks:
                                        continue
                                    seen_addr_pks.add(_addr_obj.pk)
                                    _append_inherited(
                                        _addr_type_key,
                                        _addr_ct,
                                        _addr_obj,
                                        ancestor,
                                        tc,
                                    )
                                if (
                                    tc.inherit_stop_on_own
                                    and _addr_type_key in covered_type_keys
                                ):
                                    break
            except Exception:
                pass

            groups = [
                {
                    "type_key": k,
                    "type_label": v["label"],
                    "count": len(v["objects"]),
                    "objects": v["objects"],
                }
                for k, v in sorted(
                    inh_links_by_type.items(), key=lambda x: x[1]["label"]
                )
            ]
            return JsonResponse(
                {"groups": groups, "total": sum(g["count"] for g in groups)}
            )

        except Exception:
            return JsonResponse({"groups": [], "total": 0})
