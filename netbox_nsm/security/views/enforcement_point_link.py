"""Assign or remove enforcement-point links stored as ``nsm_object_link`` COT rows."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import View

from netbox_nsm.forms import EnforcementPointInterfaceAssignForm
from netbox_nsm.security.links.object_link_service import (
    create_or_update_enforcement_point_link,
    delete_enforcement_point_link,
    get_enforcement_point_link_by_pk,
    iter_enforcement_point_links_for_interface,
    object_link_permission,
)

__all__ = ("EnforcementPointInterfaceAssignView", "EnforcementPointLinkDeleteView")


def _resolve_object(ct_id, obj_id):
    try:
        ct = ContentType.objects.get(pk=int(ct_id))
        return ct, ct.get_object_for_this_type(pk=int(obj_id))
    except Exception:
        return None, None


class EnforcementPointInterfaceAssignView(LoginRequiredMixin, View):
    """Assign NSM policy objects to an interface as enforcement-point links."""

    template_name = "netbox_nsm/object_link_assign.html"

    def _permission_required(self):
        return object_link_permission("add")

    def dispatch(self, request, *args, **kwargs):
        perm = self._permission_required()
        if perm and not request.user.has_perm(perm):
            messages.error(request, _("Permission denied."))
            return HttpResponseRedirect(request.GET.get("return_url", "/"))
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, slug: str):
        ct_id = request.GET.get("ct_id", "")
        obj_id = request.GET.get("obj_id", "")
        return_url = request.GET.get("return_url", "/")
        ct, obj = _resolve_object(ct_id, obj_id)
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
        if request.GET.get("object_b_id"):
            try:
                b_ct = ContentType.objects.get(pk=int(request.GET["object_b_type_id"]))
                prefill_object_b = b_ct.get_object_for_this_type(
                    pk=int(request.GET["object_b_id"])
                )
            except Exception:
                prefill_object_b = None

        form = EnforcementPointInterfaceAssignForm(initial=initial, source_object=obj)
        existing = list(iter_enforcement_point_links_for_interface(obj, slug))
        return self._render(
            request,
            slug,
            form,
            obj,
            existing,
            return_url,
            prefill_object_b=prefill_object_b,
        )

    def post(self, request, slug: str):
        ct_id = request.POST.get("object_a_type_id", "")
        obj_id = request.POST.get("object_a_id", "")
        return_url = request.POST.get("return_url", "/")
        ct, obj = _resolve_object(ct_id, obj_id)
        if obj is None:
            messages.error(request, _("Object not found."))
            return HttpResponseRedirect(return_url)

        form = EnforcementPointInterfaceAssignForm(request.POST, source_object=obj)
        existing = list(iter_enforcement_point_links_for_interface(obj, slug))

        if not form.is_valid():
            return self._render(
                request,
                slug,
                form,
                obj,
                existing,
                return_url,
                prefill_object_b=None,
            )

        b_ct_pk = form.cleaned_data["object_b_type"]
        comment = form.cleaned_data.get("comment", "")

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
                slug,
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
                slug,
                form,
                obj,
                existing,
                return_url,
                prefill_object_b=None,
            )

        created_count = 0
        errors = 0
        for b_obj_id in b_obj_ids:
            try:
                policy_obj = b_ct.get_object_for_this_type(pk=b_obj_id)
            except Exception:
                errors += 1
                continue
            try:
                _link, created = create_or_update_enforcement_point_link(
                    obj,
                    slug,
                    policy_object=policy_obj,
                    comment=comment,
                )
            except Exception as exc:
                errors += 1
                messages.error(
                    request,
                    _("Could not save enforcement point for %(obj)s: %(error)s")
                    % {"obj": policy_obj, "error": exc},
                )
                continue
            if created:
                created_count += 1

        if created_count:
            messages.success(request, _("{n} link(s) created.").format(n=created_count))
        elif errors:
            return self._render(
                request,
                slug,
                form,
                obj,
                existing,
                return_url,
                prefill_object_b=None,
            )
        else:
            messages.warning(request, _("All links already existed."))

        return HttpResponseRedirect(return_url)

    def _render(
        self,
        request,
        slug: str,
        form,
        obj,
        existing,
        return_url,
        *,
        prefill_object_b=None,
    ):
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
                "hide_propagation": True,
                "page_title": _("Assign Enforcement Point"),
                "enforcement_point_mode": True,
                "rulebook_slug": slug,
            },
        )


class EnforcementPointLinkDeleteView(LoginRequiredMixin, View):
    template_name = "generic/object_delete.html"

    def dispatch(self, request, *args, **kwargs):
        perm = object_link_permission("delete")
        if perm and not request.user.has_perm(perm):
            messages.error(request, _("Permission denied."))
            return HttpResponseRedirect(request.GET.get("return_url", "/"))
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        link = get_enforcement_point_link_by_pk(pk)
        if link is None:
            messages.error(request, _("Enforcement point link not found."))
            return HttpResponseRedirect(request.GET.get("return_url", "/"))
        return render(
            request,
            self.template_name,
            {
                "object": link.instance,
                "return_url": request.GET.get("return_url", "/"),
            },
        )

    def post(self, request, pk):
        link = get_enforcement_point_link_by_pk(pk)
        return_url = request.POST.get("return_url", "/")
        if link is None:
            messages.error(request, _("Enforcement point link not found."))
            return HttpResponseRedirect(return_url)
        delete_enforcement_point_link(link)
        messages.success(request, _("Enforcement point assignment removed."))
        return HttpResponseRedirect(return_url)
