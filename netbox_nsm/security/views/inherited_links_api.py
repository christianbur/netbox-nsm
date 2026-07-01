from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse, HttpResponseBadRequest
from django.views import View

from netbox_nsm.objects.group_inheritance import iter_inherited_group_nsm_links
from netbox_nsm.addresses.ipam_inheritance import iter_inherited_nsm_links

__all__ = ("InheritedLinksApiView",)


class InheritedLinksApiView(LoginRequiredMixin, View):
    """
    JSON endpoint for inherited NSM links (group member-of + IPAM prefix).

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
            from netbox_nsm.core.display_utils import (
                get_display_template_map,
                render_object_display,
                tc_panel_label,
            )

            tmpl_map = get_display_template_map()
            inh_links_by_type: dict = {}

            def _collect(item):
                linked = item.linked
                lct = item.linked_ct
                type_key = item.type_key
                ancestor = item.ancestor
                tc = item.tc

                if type_key not in inh_links_by_type:
                    inh_links_by_type[type_key] = {
                        "label": tc_panel_label(lct, tc),
                        "objects": [],
                    }
                inh_links_by_type[type_key]["objects"].append(
                    {
                        "url": (
                            linked.get_absolute_url()
                            if hasattr(linked, "get_absolute_url")
                            else "#"
                        ),
                        "name": render_object_display(linked, lct.pk, tmpl_map),
                        "inherited_from_url": ancestor.get_absolute_url(),
                        "inherited_from_name": str(ancestor),
                    }
                )

            for item in iter_inherited_group_nsm_links(obj):
                _collect(item)

            if isinstance(obj, (IPAddress, IPRange, Prefix)):
                for item in iter_inherited_nsm_links(obj):
                    _collect(item)

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
