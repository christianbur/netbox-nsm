"""Assign or remove rulebook links stored as ``nsm_object_link`` COT rows."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View

from netbox_nsm.security.links.object_link_service import (
    create_or_update_rulebook_link,
    delete_rulebook_link,
    get_rulebook_link_by_pk,
    object_link_permission,
)
from netbox_nsm.rulebooks.forms.rulebook_link import RulebookLinkAssignForm

__all__ = ("RulebookLinkAssignView", "RulebookLinkDeleteView")


def _resolve_object(ct_id, obj_id):
    try:
        ct = ContentType.objects.get(pk=int(ct_id))
        return ct, ct.get_object_for_this_type(pk=int(obj_id))
    except Exception:
        return None, None


class RulebookLinkAssignView(LoginRequiredMixin, View):
    template_name = "netbox_nsm/rulebook_link_assign.html"

    def _permission_required(self):
        return object_link_permission("add")

    def dispatch(self, request, *args, **kwargs):
        perm = self._permission_required()
        if perm and not request.user.has_perm(perm):
            messages.error(request, _("Permission denied."))
            return HttpResponseRedirect(request.GET.get("return_url", "/"))
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        ct_id = request.GET.get("ct_id", "")
        obj_id = request.GET.get("obj_id", "")
        return_url = request.GET.get("return_url", "/")
        ct, obj = _resolve_object(ct_id, obj_id)
        if obj is None:
            messages.error(request, _("Object not found."))
            return HttpResponseRedirect(return_url)
        form = RulebookLinkAssignForm()
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "object": obj,
                "content_type": ct,
                "return_url": return_url,
            },
        )

    def post(self, request):
        ct_id = request.POST.get("ct_id", "")
        obj_id = request.POST.get("obj_id", "")
        return_url = request.POST.get("return_url", "/")
        ct, obj = _resolve_object(ct_id, obj_id)
        if obj is None:
            messages.error(request, _("Object not found."))
            return HttpResponseRedirect(return_url)
        form = RulebookLinkAssignForm(request.POST)
        if form.is_valid():
            slug = form.cleaned_data["rulebook_slug"]
            create_or_update_rulebook_link(obj, slug)
            messages.success(request, _("Rulebook assigned."))
            return HttpResponseRedirect(return_url)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "object": obj,
                "content_type": ct,
                "return_url": return_url,
            },
        )


class RulebookLinkDeleteView(LoginRequiredMixin, View):
    template_name = "generic/object_delete.html"

    def dispatch(self, request, *args, **kwargs):
        perm = object_link_permission("delete")
        if perm and not request.user.has_perm(perm):
            messages.error(request, _("Permission denied."))
            return HttpResponseRedirect(request.GET.get("return_url", "/"))
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        link = get_rulebook_link_by_pk(pk)
        if link is None:
            messages.error(request, _("Rulebook link not found."))
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
        link = get_rulebook_link_by_pk(pk)
        return_url = request.POST.get("return_url", "/")
        if link is None:
            messages.error(request, _("Rulebook link not found."))
            return HttpResponseRedirect(return_url)
        delete_rulebook_link(link)
        messages.success(request, _("Rulebook assignment removed."))
        return HttpResponseRedirect(return_url)
