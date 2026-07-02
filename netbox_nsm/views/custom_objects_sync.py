"""Deprecated sync views — use Bundles schema apply instead."""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View

from netbox_nsm.core.setup_flags import setup_menu_enabled

__all__ = ("SyncBuiltinToCustomObjectsView", "SyncTypeConfigsView")


class SyncBuiltinToCustomObjectsView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        if not setup_menu_enabled():
            raise Http404
        messages.info(
            request,
            _("Use Bundles → NSM Schema → Apply instead of legacy sync."),
        )
        return redirect(reverse("plugins:netbox_nsm:bundle_detail", args=["nsm_schema"]))


class SyncTypeConfigsView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        if not setup_menu_enabled():
            raise Http404
        messages.info(
            request,
            _(
                "Type metadata is applied with schema bundles "
                "(metadata.types / metadata.rulebooks → COT comments)."
            ),
        )
        return redirect(reverse("plugins:netbox_nsm:bundles"))
