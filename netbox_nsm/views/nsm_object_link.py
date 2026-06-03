from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponseRedirect, JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View

from netbox.views import generic
from netbox_nsm.forms import NSMObjectLinkAssignForm
from netbox_nsm.models import NSMObjectLink, NSMTypeConfig, TypeConfig

__all__ = (
    "NSMObjectLinkAssignView",
    "NSMObjectLinkEditView",
    "NSMObjectLinkDeleteView",
    "NSMObjectTypeElementsApiView",
)


class NSMObjectLinkAssignView(LoginRequiredMixin, View):
    """
    Page opened by the 'Assign' button in the Security panel.

    GET  /plugins/netbox-nsm/object-link/assign/?ct_id=X&obj_id=Y&return_url=...
    POST /plugins/netbox-nsm/object-link/assign/
    """

    template_name = "netbox_nsm/nsm_object_link_assign.html"

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

        form = NSMObjectLinkAssignForm(
            initial={
                "object_a_type_id": ct_id,
                "object_a_id": obj_id,
            }
        )

        # Existing links for object_a
        ct_real = ContentType.objects.get_for_model(obj)
        existing = (
            NSMObjectLink.objects.filter(object_a_type=ct_real, object_a_id=obj.pk)
            .select_related("object_b_type")
            .order_by("created")
        )

        return self._render(request, form, obj, existing, return_url)

    def post(self, request):
        form = NSMObjectLinkAssignForm(request.POST)
        ct_id = request.POST.get("object_a_type_id", "")
        obj_id = request.POST.get("object_a_id", "")
        return_url = request.POST.get("return_url", "/")

        ct, obj = self._resolve_object(ct_id, obj_id)
        if obj is None:
            messages.error(request, _("Object not found."))
            return HttpResponseRedirect(return_url)

        ct_real = ContentType.objects.get_for_model(obj)
        existing = (
            NSMObjectLink.objects.filter(object_a_type=ct_real, object_a_id=obj.pk)
            .select_related("object_b_type")
            .order_by("created")
        )

        if not form.is_valid():
            return self._render(request, form, obj, existing, return_url)

        b_ct_pk = form.cleaned_data["object_b_type"]
        comment = form.cleaned_data.get("comment", "")

        # Support multiple selected IDs (list of hidden inputs named object_b_id)
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
            return self._render(request, form, obj, existing, return_url)

        try:
            b_ct = ContentType.objects.get(pk=int(b_ct_pk))
        except ContentType.DoesNotExist:
            form.add_error("object_b_type", _("Invalid type."))
            return self._render(request, form, obj, existing, return_url)

        created_count = 0
        for b_obj_id in b_obj_ids:
            link, created = NSMObjectLink.objects.get_or_create(
                object_a_type=ct_real,
                object_a_id=obj.pk,
                object_b_type=b_ct,
                object_b_id=b_obj_id,
                defaults={"comment": comment},
            )
            if not created:
                if link.comment != comment:
                    link.comment = comment
                    link.save(update_fields=["comment", "last_updated"])
            else:
                created_count += 1

        if created_count:
            messages.success(request, _("{n} link(s) created.").format(n=created_count))
        else:
            messages.warning(request, _("All links already existed."))

        return HttpResponseRedirect(return_url)

    def _render(self, request, form, obj, existing, return_url):
        from django.shortcuts import render

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "object_a": obj,
                "existing_links": existing,
                "return_url": return_url,
            },
        )


class NSMObjectLinkEditView(LoginRequiredMixin, View):
    """
    Edit the comment of an existing NSMObjectLink.

    GET  /plugins/netbox-nsm/object-link/<pk>/edit/?return_url=...
    POST /plugins/netbox-nsm/object-link/<pk>/edit/
    """

    template_name = "netbox_nsm/nsm_object_link_edit.html"

    def get(self, request, pk):
        link = get_object_or_404(NSMObjectLink, pk=pk)
        return_url = request.GET.get("return_url", "/")
        from django import forms as dj_forms

        class _Form(dj_forms.Form):
            comment = dj_forms.CharField(
                label=_("Comment"),
                required=False,
                widget=dj_forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            )

        form = _Form(initial={"comment": link.comment or ""})
        from django.shortcuts import render

        return render(
            request,
            self.template_name,
            {"form": form, "link": link, "return_url": return_url},
        )

    def post(self, request, pk):
        link = get_object_or_404(NSMObjectLink, pk=pk)
        return_url = request.POST.get("return_url", "/")
        from django import forms as dj_forms

        class _Form(dj_forms.Form):
            comment = dj_forms.CharField(
                label=_("Comment"),
                required=False,
                widget=dj_forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            )

        form = _Form(request.POST)
        if form.is_valid():
            link.comment = form.cleaned_data.get("comment", "")
            link.save(update_fields=["comment", "last_updated"])
            messages.success(request, _("Comment updated."))
            return HttpResponseRedirect(return_url)

        from django.shortcuts import render

        return render(
            request,
            self.template_name,
            {"form": form, "link": link, "return_url": return_url},
        )


class NSMObjectLinkDeleteView(LoginRequiredMixin, View):
    """
    GET  /plugins/netbox-nsm/object-link/<int:pk>/delete/?return_url=...  → confirmation page
    POST /plugins/netbox-nsm/object-link/<int:pk>/delete/                 → delete and redirect
    """

    def get(self, request, pk):
        link = get_object_or_404(NSMObjectLink, pk=pk)
        return_url = request.GET.get("return_url", "/")
        from django.shortcuts import render
        return render(
            request,
            "netbox_nsm/nsm_object_link_delete.html",
            {"link": link, "return_url": return_url},
        )

    def post(self, request, pk):
        return_url = request.POST.get("return_url", "/")
        link = get_object_or_404(NSMObjectLink, pk=pk)
        link.delete()
        messages.success(request, _("Link deleted."))
        return HttpResponseRedirect(return_url)


class NSMObjectTypeElementsApiView(LoginRequiredMixin, View):
    """
    AJAX endpoint: returns all instances of an NSMTypeConfig type as JSON.

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

        # Only allow TypeConfig-configured types with panel_linkable=True
        if not TypeConfig.objects.filter(content_type=ct, panel_linkable=True).exists():
            return HttpResponseBadRequest("Type not configured as panel-linkable in NSM")

        q = request.GET.get("q", "").strip()
        model_class = ct.model_class()
        if model_class is None:
            return JsonResponse({"results": []})

        qs = model_class.objects.all()
        # Try name/display filtering if a name field exists
        if q:
            for field_name in ("name", "display", "prefix", "address"):
                try:
                    qs = model_class.objects.filter(**{f"{field_name}__icontains": q})
                    break
                except Exception:
                    continue

        results = []
        for obj in qs[:100]:
            display = str(obj)
            results.append({"id": obj.pk, "display": display})

        return JsonResponse({"results": results})
