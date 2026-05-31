from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse, HttpResponseBadRequest
from django.views import View

from netbox_nsm.models import NSMObjectLink

__all__ = ("InheritedLinksApiView",)

# Hard cap on ancestor depth – prevents runaway queries on flat /24-heavy
# IPAM designs.  30 levels is more than enough for any real prefix hierarchy.
_MAX_ANCESTORS = 30


class InheritedLinksApiView(View):
    """
    JSON endpoint that returns NSMObjectLinks inherited from containing Prefixes
    for an IPAM object (IPAddress, IPRange, or Prefix).

    GET /plugins/netbox-nsm/api/inherited-links/
        ?ct_id=<int>&obj_id=<int>

    Response:
        {
            "groups": [
                {
                    "type_key":   "netbox_custom_objects__table3model",
                    "type_label": "Custom Objects › Labels",
                    "count": 2,
                    "objects": [
                        {
                            "url":                  "/...",
                            "name":                 "test",
                            "inherited_from_url":   "/ipam/prefixes/1/",
                            "inherited_from_name":  "10.0.0.0/8"
                        }
                    ]
                }
            ],
            "total": 2
        }
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
                ct_display_label,
            )
            from django.db.models import prefetch_related_objects

            # Load all TypeConfigs once – avoids one DB hit per link in the loop
            tc_map = {
                tc.content_type_id: tc
                for tc in _TypeConfig.objects.select_related("content_type").all()
            }
            tmpl_map = get_display_template_map()

            # ── Determine ancestor Prefixes ───────────────────────────────
            ancestor_prefixes: list = []
            if isinstance(obj, IPAddress):
                ip_str = str(obj.address).split("/")[0]
                candidates = list(
                    Prefix.objects.filter(prefix__net_contains=ip_str)
                    .order_by()[:_MAX_ANCESTORS]
                )
                candidates.sort(key=lambda p: p.prefix.prefixlen, reverse=True)
                ancestor_prefixes = candidates
            elif isinstance(obj, IPRange):
                start_str = str(obj.start_address).split("/")[0]
                candidates = list(
                    Prefix.objects.filter(prefix__net_contains=start_str)
                    .order_by()[:_MAX_ANCESTORS]
                )
                candidates.sort(key=lambda p: p.prefix.prefixlen, reverse=True)
                ancestor_prefixes = candidates
            elif isinstance(obj, Prefix):
                ip_str = str(obj.prefix.ip)
                candidates = list(
                    Prefix.objects.filter(prefix__net_contains=ip_str)
                    .exclude(pk=obj.pk)
                    .order_by()[:_MAX_ANCESTORS]
                )
                candidates.sort(key=lambda p: p.prefix.prefixlen, reverse=True)
                ancestor_prefixes = candidates

            if not ancestor_prefixes:
                return JsonResponse({"groups": [], "total": 0})

            # ── Seed covered_type_keys from the object's own direct links ─
            # Used for inherit_stop_on_own logic.
            direct_fwd = list(
                NSMObjectLink.objects.filter(object_a_type=ct, object_a_id=obj_id)
                .select_related("object_b_type")
            )
            direct_rev = list(
                NSMObjectLink.objects.filter(object_b_type=ct, object_b_id=obj_id)
                .select_related("object_a_type")
            )
            covered_type_keys: set = set()
            for link in direct_fwd:
                lct = link.object_b_type
                covered_type_keys.add(f"{lct.app_label}__{lct.model}")
            for link in direct_rev:
                lct = link.object_a_type
                covered_type_keys.add(f"{lct.app_label}__{lct.model}")

            prefix_ct = ContentType.objects.get_for_model(ancestor_prefixes[0])
            inh_links_by_type: dict = {}

            for ancestor in ancestor_prefixes:
                for direction in ("fwd", "rev"):
                    if direction == "fwd":
                        qs_inh = list(
                            NSMObjectLink.objects.filter(
                                object_a_type=prefix_ct, object_a_id=ancestor.pk
                            ).select_related("object_b_type")
                        )
                        # Batch-resolve Generic FK in one query per content-type
                        prefetch_related_objects(qs_inh, "object_b")
                    else:
                        qs_inh = list(
                            NSMObjectLink.objects.filter(
                                object_b_type=prefix_ct, object_b_id=ancestor.pk
                            ).select_related("object_a_type")
                        )
                        prefetch_related_objects(qs_inh, "object_a")

                    for link in qs_inh:
                        linked = link.object_b if direction == "fwd" else link.object_a
                        if linked is None:
                            continue
                        lct = (
                            link.object_b_type if direction == "fwd" else link.object_a_type
                        )
                        type_key = f"{lct.app_label}__{lct.model}"

                        tc = tc_map.get(lct.id)
                        if tc is None or not tc.inherit_links:
                            continue
                        if tc.inherit_stop_on_own and type_key in covered_type_keys:
                            continue

                        obj_url = (
                            linked.get_absolute_url()
                            if hasattr(linked, "get_absolute_url")
                            else "#"
                        )
                        if type_key not in inh_links_by_type:
                            inh_links_by_type[type_key] = {
                                "label": ct_display_label(lct),
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

            # ── Also inherit nsm_addresses objects via FK ─────────────────
            try:
                from netbox_custom_objects.models import CustomObjectType as _COT

                _addr_cot = _COT.objects.filter(slug="nsm_addresses").first()
                if _addr_cot:
                    _AddrModel = _addr_cot.get_model()
                    _addr_ct = ContentType.objects.get_for_model(_AddrModel)
                    _addr_type_key = f"{_addr_ct.app_label}__{_addr_ct.model}"
                    tc = tc_map.get(_addr_ct.id)
                    if tc and tc.inherit_links:
                        if not (tc.inherit_stop_on_own and _addr_type_key in covered_type_keys):
                            for ancestor in ancestor_prefixes:
                                for _addr_obj in _AddrModel.objects.filter(
                                    prefix_id=ancestor.pk
                                ):
                                    if _addr_type_key not in inh_links_by_type:
                                        inh_links_by_type[_addr_type_key] = {
                                            "label": ct_display_label(_addr_ct),
                                            "objects": [],
                                        }
                                        covered_type_keys.add(_addr_type_key)
                                    inh_links_by_type[_addr_type_key]["objects"].append(
                                        {
                                            "url": (
                                                _addr_obj.get_absolute_url()
                                                if hasattr(_addr_obj, "get_absolute_url")
                                                else "#"
                                            ),
                                            "name": render_object_display(
                                                _addr_obj, _addr_ct.pk, tmpl_map
                                            ),
                                            "inherited_from_url": ancestor.get_absolute_url(),
                                            "inherited_from_name": str(ancestor),
                                        }
                                    )
                                if tc.inherit_stop_on_own and _addr_type_key in covered_type_keys:
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
                for k, v in sorted(inh_links_by_type.items(), key=lambda x: x[1]["label"])
            ]
            return JsonResponse({"groups": groups, "total": sum(g["count"] for g in groups)})

        except Exception:
            return JsonResponse({"groups": [], "total": 0})
