from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponseRedirect, JsonResponse, HttpResponseBadRequest
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View

from netbox_nsm.forms import ObjectLinkAssignForm, ObjectLinkEditForm
from netbox_nsm.models import TypeConfig
from netbox_nsm.objects.link_propagation import CotObjectLinkPropagationChoices
from netbox_nsm.objects.object_link_service import (
    create_or_update_links,
    delete_link,
    get_link_by_pk,
    iter_links_stored_on_netbox_object,
    update_link,
)
from netbox_nsm.objects.picker_browse import MIN_PICKER_QUERY_LEN, browse_content_type_objects

__all__ = (
    "ObjectLinkAssignView",
    "ObjectLinkEditView",
    "ObjectLinkDeleteView",
    "ObjectTypeElementsApiView",
)


class ObjectLinkAssignView(LoginRequiredMixin, View):
    """
    Page opened by the 'Assign' button in the Security panel.

    GET  /plugins/netbox-nsm/object-link/assign/?ct_id=X&obj_id=Y&return_url=...
    POST /plugins/netbox-nsm/object-link/assign/
    """

    template_name = "netbox_nsm/object_link_assign.html"

    def _resolve_object(self, ct_id, obj_id):
        try:
            ct = ContentType.objects.get(pk=int(ct_id))
            obj = ct.get_object_for_this_type(pk=int(obj_id))
            return ct, obj
        except Exception:
            return None, None

    def get(self, request):
        ct_id = request.GET.get("ct_id", "")
        obj_id = request.GET.get("obj_id", "")
        return_url = request.GET.get("return_url", "/")

        ct, obj = self._resolve_object(ct_id, obj_id)
        if obj is None:
            messages.error(request, _("Object not found."))
            return HttpResponseRedirect(return_url)

        initial = {
            "object_a_type_id": ct_id,
            "object_a_id": obj_id,
        }
        prefill_object_b = None
        if request.GET.get("object_b_type_id"):
            initial["object_b_type"] = request.GET["object_b_type_id"]
        if request.GET.get("comment"):
            initial["comment"] = request.GET["comment"]
        if request.GET.get("propagation"):
            initial["propagation"] = request.GET["propagation"]
        if request.GET.get("object_b_id"):
            try:
                b_ct = ContentType.objects.get(pk=int(request.GET["object_b_type_id"]))
                prefill_object_b = b_ct.get_object_for_this_type(
                    pk=int(request.GET["object_b_id"])
                )
            except Exception:
                prefill_object_b = None

        form = ObjectLinkAssignForm(initial=initial, source_object=obj)
        existing = list(iter_links_stored_on_netbox_object(obj))

        return self._render(
            request,
            form,
            obj,
            existing,
            return_url,
            prefill_object_b=prefill_object_b,
        )

    def post(self, request):
        ct_id = request.POST.get("object_a_type_id", "")
        obj_id = request.POST.get("object_a_id", "")
        return_url = request.POST.get("return_url", "/")

        ct, obj = self._resolve_object(ct_id, obj_id)
        if obj is None:
            messages.error(request, _("Object not found."))
            return HttpResponseRedirect(return_url)

        form = ObjectLinkAssignForm(request.POST, source_object=obj)
        existing = list(iter_links_stored_on_netbox_object(obj))

        if not form.is_valid():
            return self._render(
                request,
                form,
                obj,
                existing,
                return_url,
                prefill_object_b=None,
            )

        b_ct_pk = form.cleaned_data["object_b_type"]
        comment = form.cleaned_data.get("comment", "")
        cot_propagation = form.cleaned_data.get(
            "propagation", CotObjectLinkPropagationChoices.DIRECT
        )

        raw_ids = request.POST.getlist("object_b_id")
        b_obj_ids = []
        for raw in raw_ids:
            try:
                val = int(raw)
                if val > 0:
                    b_obj_ids.append(val)
            except (ValueError, TypeError):
                pass

        if not b_obj_ids:
            form.add_error(None, _("Please select at least one object."))
            return self._render(
                request,
                form,
                obj,
                existing,
                return_url,
                prefill_object_b=None,
            )

        try:
            b_ct = ContentType.objects.get(pk=int(b_ct_pk))
        except ContentType.DoesNotExist:
            form.add_error("object_b_type", _("Invalid type."))
            return self._render(
                request,
                form,
                obj,
                existing,
                return_url,
                prefill_object_b=None,
            )

        created_count = 0
        for b_obj_id in b_obj_ids:
            try:
                policy_obj = b_ct.get_object_for_this_type(pk=b_obj_id)
            except Exception:
                continue
            _link, created = create_or_update_links(
                obj,
                policy_obj,
                cot_propagation=cot_propagation,
                comment=comment,
            )
            if created:
                created_count += 1

        if created_count:
            messages.success(request, _("{n} link(s) created.").format(n=created_count))
        else:
            messages.warning(request, _("All links already existed."))

        return HttpResponseRedirect(return_url)

    def _render(
        self,
        request,
        form,
        obj,
        existing,
        return_url,
        *,
        prefill_object_b=None,
    ):
        from django.shortcuts import render

        prefill_object_b_id = ""
        prefill_object_b_display = ""
        if prefill_object_b is not None:
            prefill_object_b_id = str(prefill_object_b.pk)
            prefill_object_b_display = str(prefill_object_b)

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "object_a": obj,
                "existing_links": existing,
                "return_url": return_url,
                "prefill_object_b_id": prefill_object_b_id,
                "prefill_object_b_display": prefill_object_b_display,
            },
        )


class ObjectLinkEditView(LoginRequiredMixin, View):
    """
    Edit propagation and comment on an existing nsm_object_link row.

    GET  /plugins/netbox-nsm/object-link/<pk>/edit/?return_url=...
    POST /plugins/netbox-nsm/object-link/<pk>/edit/
    """

    template_name = "netbox_nsm/object_link_edit.html"

    def _form_initial(self, link):
        return {
            "comment": link.comment or "",
            "propagation": link.cot_propagation,
        }

    def get(self, request, pk):
        link = get_link_by_pk(pk)
        if link is None:
            from django.http import Http404

            raise Http404
        return_url = request.GET.get("return_url", "/")
        form = ObjectLinkEditForm(
            initial=self._form_initial(link),
            source_object=link.object_a,
        )
        from django.shortcuts import render

        return render(
            request,
            self.template_name,
            {"form": form, "link": link, "return_url": return_url},
        )

    def post(self, request, pk):
        link = get_link_by_pk(pk)
        if link is None:
            from django.http import Http404

            raise Http404
        return_url = request.POST.get("return_url", "/")
        form = ObjectLinkEditForm(
            request.POST,
            source_object=link.object_a,
        )
        if form.is_valid():
            update_link(
                link,
                cot_propagation=form.cleaned_data.get(
                    "propagation", CotObjectLinkPropagationChoices.DIRECT
                ),
                comment=form.cleaned_data.get("comment", ""),
            )
            messages.success(request, _("Link updated."))
            return HttpResponseRedirect(return_url)

        from django.shortcuts import render

        return render(
            request,
            self.template_name,
            {"form": form, "link": link, "return_url": return_url},
        )


class ObjectLinkDeleteView(LoginRequiredMixin, View):
    """
    GET  /plugins/netbox-nsm/object-link/<int:pk>/delete/?return_url=...  → confirmation page
    POST /plugins/netbox-nsm/object-link/<int:pk>/delete/                 → delete and redirect
    """

    def get(self, request, pk):
        link = get_link_by_pk(pk)
        if link is None:
            from django.http import Http404

            raise Http404
        return_url = request.GET.get("return_url", "/")
        from django.shortcuts import render

        return render(
            request,
            "netbox_nsm/object_link_delete.html",
            {"link": link, "return_url": return_url},
        )

    def post(self, request, pk):
        return_url = request.POST.get("return_url", "/")
        link = get_link_by_pk(pk)
        if link is None:
            from django.http import Http404

            raise Http404
        delete_link(link)
        messages.success(request, _("Assignment removed."))
        return HttpResponseRedirect(return_url)


class ObjectTypeElementsApiView(LoginRequiredMixin, View):
    """
    AJAX endpoint: returns all instances of a TypeConfig type as JSON.

    GET /plugins/netbox-nsm/api/type-elements/?ct_id=X&q=...
    """

    def get(self, request):
        try:
            ct_id = int(request.GET["ct_id"])
        except (KeyError, ValueError):
            return HttpResponseBadRequest("ct_id required")

        try:
            ct = ContentType.objects.get(pk=ct_id)
        except ContentType.DoesNotExist:
            return HttpResponseBadRequest("Invalid ct_id")

        if not TypeConfig.queryset_panel_linkable().filter(content_type=ct).exists():
            return HttpResponseBadRequest(
                "Type not configured as panel-linkable in NSM"
            )

        assigner_ct_id = request.GET.get("assigner_ct_id")
        if assigner_ct_id:
            try:
                assigner_id = int(assigner_ct_id)
            except (TypeError, ValueError):
                return HttpResponseBadRequest("Invalid assigner_ct_id")
            if (
                not TypeConfig.queryset_assignable_from(assigner_id)
                .filter(content_type=ct)
                .exists()
            ):
                return HttpResponseBadRequest(
                    "Type not assignable from this object type in NSM"
                )

        q_raw = request.GET.get("q", "").strip()
        wildcard = q_raw == "*"
        q = "" if wildcard else q_raw
        if q and len(q) < MIN_PICKER_QUERY_LEN:
            return JsonResponse(
                {
                    "results": [],
                    "has_more": False,
                    "count": 0,
                    "error": "min_query",
                }
            )

        try:
            limit = max(1, min(int(request.GET.get("limit", 30)), 100))
        except (TypeError, ValueError):
            limit = 30
        try:
            offset = max(0, int(request.GET.get("offset", 0)))
        except (TypeError, ValueError):
            offset = 0

        try:
            payload = browse_content_type_objects(
                ct_id, q=q, limit=limit, offset=offset
            )
        except ValueError as exc:
            return HttpResponseBadRequest(str(exc))

        count = payload["count"]
        results = [
            {"id": item["id"], "display": item["display"]}
            for item in payload["results"]
        ]
        has_more = offset + len(results) < count
        return JsonResponse({"results": results, "has_more": has_more, "count": count})
