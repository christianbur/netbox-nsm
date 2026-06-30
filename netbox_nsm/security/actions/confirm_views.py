"""Confirmation views for Security Panel non-ObjectLink row actions."""

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views import View
from utilities.forms.fields import DynamicModelChoiceField

from netbox_nsm.addresses.address_ipam_fk import (
    NSM_ADDRESSES_SLUG,
    get_nsm_address_model,
    panel_link_type_for_address_ipam_fk,
)
from netbox_nsm.type_metadata.permissions import (
    can_change_cot_instance,
    can_delete_cot_instance,
)

__all__ = (
    "AddressIpamFkClearView",
    "AddressIpamFkEditView",
    "GroupM2mEditView",
    "GroupM2mRemoveView",
)

_IPAM_FIELD_MODELS = {
    "prefix": ("ipam.models", "Prefix"),
    "ip_address": ("ipam.models", "IPAddress"),
    "range": ("ipam.models", "IPRange"),
}


def _load_ipam_model(field_name: str):
    import importlib

    module_path, class_name = _IPAM_FIELD_MODELS[field_name]
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _make_address_ipam_fk_edit_form(field_name: str, initial_ipam):
    ipam_model = _load_ipam_model(field_name)

    class AddressIpamFkEditForm(forms.Form):
        ipam_target = DynamicModelChoiceField(
            queryset=ipam_model.objects.all(),
            required=True,
            label=panel_link_type_for_address_ipam_fk(field_name),
        )

    return AddressIpamFkEditForm(initial={"ipam_target": initial_ipam})


def _make_group_m2m_edit_form(group_obj, initial_group):
    group_model = type(group_obj)

    class GroupM2mEditForm(forms.Form):
        new_group = DynamicModelChoiceField(
            queryset=group_model.objects.all(),
            required=True,
            label=_("Group"),
        )

    return GroupM2mEditForm(initial={"new_group": initial_group})


def _load_content_object(ct_id: int, obj_id: int):
    ct = get_object_or_404(ContentType, pk=ct_id)
    model = ct.model_class()
    if model is None:
        return None, None
    return ct, get_object_or_404(model, pk=obj_id)


def _deny_panel_action(request, return_url: str):
    messages.error(request, _("Permission denied."))
    return HttpResponseRedirect(return_url or "/")


class AddressIpamFkClearView(LoginRequiredMixin, View):
    """
    Clear an IPAM FK field on ``nsm_addresses`` (remove panel assignment).

    GET/POST /plugins/netbox-nsm/panel-link/address-ipam-fk/<slug>/clear/
        ?addr_ct_id=&addr_id=&field=&return_url=
    """

    template_name = "netbox_nsm/address_ipam_fk_clear.html"

    _ALLOWED_FIELDS = frozenset({"prefix", "ip_address", "range"})

    def _context(self, request, addr_obj, field_name, return_url):
        from django.contrib.contenttypes.models import ContentType

        from netbox_nsm.addresses.address_ipam_fk import panel_link_type_for_address_ipam_fk

        ipam_obj = getattr(addr_obj, field_name, None)
        return {
            "addr_obj": addr_obj,
            "addr_ct_id": ContentType.objects.get_for_model(addr_obj).pk,
            "field_name": field_name,
            "field_label": panel_link_type_for_address_ipam_fk(field_name),
            "ipam_obj": ipam_obj,
            "return_url": return_url,
        }

    def get(self, request, slug):
        if slug != NSM_ADDRESSES_SLUG:
            return HttpResponseBadRequest("Unsupported address type")

        try:
            addr_ct_id = int(request.GET["addr_ct_id"])
            addr_id = int(request.GET["addr_id"])
            field_name = request.GET["field"]
        except (KeyError, ValueError):
            return HttpResponseBadRequest("addr_ct_id, addr_id and field are required")

        if field_name not in self._ALLOWED_FIELDS:
            return HttpResponseBadRequest("Invalid field")

        _, addr_obj = _load_content_object(addr_ct_id, addr_id)
        addr_model = get_nsm_address_model()
        if addr_model is None or not isinstance(addr_obj, addr_model):
            return HttpResponseBadRequest("Invalid address object")

        return_url = request.GET.get("return_url", "/")
        if not can_delete_cot_instance(request.user, addr_obj):
            return _deny_panel_action(request, return_url)

        return render(
            request,
            self.template_name,
            self._context(request, addr_obj, field_name, return_url),
        )

    def post(self, request, slug):
        if slug != NSM_ADDRESSES_SLUG:
            return HttpResponseBadRequest("Unsupported address type")

        try:
            addr_ct_id = int(request.POST["addr_ct_id"])
            addr_id = int(request.POST["addr_id"])
            field_name = request.POST["field"]
        except (KeyError, ValueError):
            return HttpResponseBadRequest("addr_ct_id, addr_id and field are required")

        if field_name not in self._ALLOWED_FIELDS:
            return HttpResponseBadRequest("Invalid field")

        _, addr_obj = _load_content_object(addr_ct_id, addr_id)
        addr_model = get_nsm_address_model()
        if addr_model is None or not isinstance(addr_obj, addr_model):
            return HttpResponseBadRequest("Invalid address object")

        return_url = request.POST.get("return_url", "/")
        if not can_delete_cot_instance(request.user, addr_obj):
            return _deny_panel_action(request, return_url)

        fk_attr = f"{field_name}_id"
        setattr(addr_obj, field_name, None)
        update_fields = [field_name, fk_attr]
        if hasattr(addr_obj, "last_updated"):
            update_fields.append("last_updated")
        addr_obj.save(update_fields=update_fields)

        return_url = request.POST.get("return_url", "/")
        messages.success(request, _("Assignment removed."))
        return HttpResponseRedirect(return_url)


class AddressIpamFkEditView(LoginRequiredMixin, View):
    """
    Change the IPAM FK target on ``nsm_addresses`` (edit panel assignment).

    GET/POST /plugins/netbox-nsm/panel-link/address-ipam-fk/<slug>/edit/
        ?addr_ct_id=&addr_id=&field=&return_url=
    """

    template_name = "netbox_nsm/address_ipam_fk_edit.html"

    _ALLOWED_FIELDS = frozenset(_IPAM_FIELD_MODELS)

    def _load_address(self, addr_ct_id, addr_id):
        _, addr_obj = _load_content_object(addr_ct_id, addr_id)
        addr_model = get_nsm_address_model()
        if addr_model is None or not isinstance(addr_obj, addr_model):
            return None
        return addr_obj

    def _context(self, request, addr_obj, field_name, return_url, form):
        ipam_obj = getattr(addr_obj, field_name, None)
        return {
            "form": form,
            "addr_obj": addr_obj,
            "addr_ct_id": ContentType.objects.get_for_model(addr_obj).pk,
            "field_name": field_name,
            "field_label": panel_link_type_for_address_ipam_fk(field_name),
            "ipam_obj": ipam_obj,
            "return_url": return_url,
        }

    def get(self, request, slug):
        if slug != NSM_ADDRESSES_SLUG:
            return HttpResponseBadRequest("Unsupported address type")

        try:
            addr_ct_id = int(request.GET["addr_ct_id"])
            addr_id = int(request.GET["addr_id"])
            field_name = request.GET["field"]
        except (KeyError, ValueError):
            return HttpResponseBadRequest("addr_ct_id, addr_id and field are required")

        if field_name not in self._ALLOWED_FIELDS:
            return HttpResponseBadRequest("Invalid field")

        addr_obj = self._load_address(addr_ct_id, addr_id)
        if addr_obj is None:
            return HttpResponseBadRequest("Invalid address object")

        return_url = request.GET.get("return_url", "/")
        if not can_change_cot_instance(request.user, addr_obj):
            return _deny_panel_action(request, return_url)
        ipam_obj = getattr(addr_obj, field_name, None)
        form = _make_address_ipam_fk_edit_form(field_name, ipam_obj)
        return render(
            request,
            self.template_name,
            self._context(request, addr_obj, field_name, return_url, form),
        )

    def post(self, request, slug):
        if slug != NSM_ADDRESSES_SLUG:
            return HttpResponseBadRequest("Unsupported address type")

        try:
            addr_ct_id = int(request.POST["addr_ct_id"])
            addr_id = int(request.POST["addr_id"])
            field_name = request.POST["field"]
        except (KeyError, ValueError):
            return HttpResponseBadRequest("addr_ct_id, addr_id and field are required")

        if field_name not in self._ALLOWED_FIELDS:
            return HttpResponseBadRequest("Invalid field")

        addr_obj = self._load_address(addr_ct_id, addr_id)
        if addr_obj is None:
            return HttpResponseBadRequest("Invalid address object")

        return_url = request.POST.get("return_url", "/")
        if not can_change_cot_instance(request.user, addr_obj):
            return _deny_panel_action(request, return_url)
        ipam_obj = getattr(addr_obj, field_name, None)
        form = _make_address_ipam_fk_edit_form(field_name, ipam_obj)
        form = type(form)(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self._context(request, addr_obj, field_name, return_url, form),
            )

        new_ipam = form.cleaned_data["ipam_target"]
        setattr(addr_obj, field_name, new_ipam)
        fk_attr = f"{field_name}_id"
        update_fields = [field_name, fk_attr]
        if hasattr(addr_obj, "last_updated"):
            update_fields.append("last_updated")
        addr_obj.save(update_fields=update_fields)

        messages.success(request, _("IPAM reference updated."))
        return HttpResponseRedirect(return_url)


class GroupM2mRemoveView(LoginRequiredMixin, View):
    """
    Remove a member from a Custom Object ``group`` M2M field.

    GET/POST /plugins/netbox-nsm/panel-link/group-m2m/remove/
        ?group_ct_id=&group_id=&member_ct_id=&member_id=&return_url=
    """

    template_name = "netbox_nsm/group_m2m_remove.html"

    def _context(self, group_obj, member_obj, return_url):
        from django.contrib.contenttypes.models import ContentType

        return {
            "group_obj": group_obj,
            "group_ct_id": ContentType.objects.get_for_model(group_obj).pk,
            "member_obj": member_obj,
            "member_ct_id": ContentType.objects.get_for_model(member_obj).pk,
            "return_url": return_url,
        }

    def get(self, request):
        try:
            group_ct_id = int(request.GET["group_ct_id"])
            group_id = int(request.GET["group_id"])
            member_ct_id = int(request.GET["member_ct_id"])
            member_id = int(request.GET["member_id"])
        except (KeyError, ValueError):
            return HttpResponseBadRequest(
                "group_ct_id, group_id, member_ct_id and member_id are required"
            )

        _, group_obj = _load_content_object(group_ct_id, group_id)
        _, member_obj = _load_content_object(member_ct_id, member_id)
        if group_obj is None or member_obj is None:
            return HttpResponseBadRequest("Invalid group or member")

        group_rel = getattr(group_obj, "group", None)
        if group_rel is None or not hasattr(group_rel, "remove"):
            return HttpResponseBadRequest("Object has no group field")

        return_url = request.GET.get("return_url", "/")
        if not can_delete_cot_instance(request.user, group_obj):
            return _deny_panel_action(request, return_url)
        return render(
            request,
            self.template_name,
            self._context(group_obj, member_obj, return_url),
        )

    def post(self, request):
        try:
            group_ct_id = int(request.POST["group_ct_id"])
            group_id = int(request.POST["group_id"])
            member_ct_id = int(request.POST["member_ct_id"])
            member_id = int(request.POST["member_id"])
        except (KeyError, ValueError):
            return HttpResponseBadRequest(
                "group_ct_id, group_id, member_ct_id and member_id are required"
            )

        _, group_obj = _load_content_object(group_ct_id, group_id)
        _, member_obj = _load_content_object(member_ct_id, member_id)
        if group_obj is None or member_obj is None:
            return HttpResponseBadRequest("Invalid group or member")

        group_rel = getattr(group_obj, "group", None)
        if group_rel is None or not hasattr(group_rel, "remove"):
            return HttpResponseBadRequest("Object has no group field")

        return_url = request.POST.get("return_url", "/")
        if not can_delete_cot_instance(request.user, group_obj):
            return _deny_panel_action(request, return_url)

        group_rel.remove(member_obj)

        messages.success(request, _("Assignment removed."))
        return HttpResponseRedirect(return_url)


class GroupM2mEditView(LoginRequiredMixin, View):
    """
    Change group membership for a Custom Object ``group`` M2M assignment.

    GET/POST /plugins/netbox-nsm/panel-link/group-m2m/edit/
        ?group_ct_id=&group_id=&member_ct_id=&member_id=&return_url=
    """

    template_name = "netbox_nsm/group_m2m_edit.html"

    def _context(self, group_obj, member_obj, return_url, form):
        return {
            "form": form,
            "group_obj": group_obj,
            "group_ct_id": ContentType.objects.get_for_model(group_obj).pk,
            "member_obj": member_obj,
            "member_ct_id": ContentType.objects.get_for_model(member_obj).pk,
            "return_url": return_url,
        }

    def _load_pair(self, group_ct_id, group_id, member_ct_id, member_id):
        _, group_obj = _load_content_object(group_ct_id, group_id)
        _, member_obj = _load_content_object(member_ct_id, member_id)
        if group_obj is None or member_obj is None:
            return None, None
        group_rel = getattr(group_obj, "group", None)
        if group_rel is None or not hasattr(group_rel, "remove"):
            return None, None
        return group_obj, member_obj

    def get(self, request):
        try:
            group_ct_id = int(request.GET["group_ct_id"])
            group_id = int(request.GET["group_id"])
            member_ct_id = int(request.GET["member_ct_id"])
            member_id = int(request.GET["member_id"])
        except (KeyError, ValueError):
            return HttpResponseBadRequest(
                "group_ct_id, group_id, member_ct_id and member_id are required"
            )

        group_obj, member_obj = self._load_pair(
            group_ct_id, group_id, member_ct_id, member_id
        )
        if group_obj is None:
            return HttpResponseBadRequest("Invalid group or member")

        return_url = request.GET.get("return_url", "/")
        if not can_change_cot_instance(request.user, group_obj):
            return _deny_panel_action(request, return_url)
        form = _make_group_m2m_edit_form(group_obj, group_obj)
        return render(
            request,
            self.template_name,
            self._context(group_obj, member_obj, return_url, form),
        )

    def post(self, request):
        try:
            group_ct_id = int(request.POST["group_ct_id"])
            group_id = int(request.POST["group_id"])
            member_ct_id = int(request.POST["member_ct_id"])
            member_id = int(request.POST["member_id"])
        except (KeyError, ValueError):
            return HttpResponseBadRequest(
                "group_ct_id, group_id, member_ct_id and member_id are required"
            )

        group_obj, member_obj = self._load_pair(
            group_ct_id, group_id, member_ct_id, member_id
        )
        if group_obj is None:
            return HttpResponseBadRequest("Invalid group or member")

        return_url = request.POST.get("return_url", "/")
        if not can_change_cot_instance(request.user, group_obj):
            return _deny_panel_action(request, return_url)
        form = _make_group_m2m_edit_form(group_obj, group_obj)
        form = type(form)(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self._context(group_obj, member_obj, return_url, form),
            )

        new_group = form.cleaned_data["new_group"]
        if new_group.pk != group_obj.pk:
            group_obj.group.remove(member_obj)
            new_group.group.add(member_obj)

        messages.success(request, _("Group membership updated."))
        return HttpResponseRedirect(return_url)
