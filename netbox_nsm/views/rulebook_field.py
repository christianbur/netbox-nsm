from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic.edit import FormView

from utilities.views import register_model_view

from netbox_nsm.forms.rulebook_field import RulebookFieldForm, RulebookFieldTypeForm
from netbox_nsm.models import RulebookField, RulebookFieldType, SecurityPolicyRulebook

__all__ = (
    "RulebookFieldAddView",
    "RulebookFieldEditView",
    "RulebookFieldDeleteView",
    "RulebookFieldTypeAddView",
    "RulebookFieldTypeEditView",
    "RulebookFieldTypeDeleteView",
)


class RulebookFieldAddView(View):
    """Add a RulebookField to a Rulebook. ?rulebook=<pk> required."""

    def _get_rulebook(self, request):
        pk = request.GET.get("rulebook") or request.POST.get("rulebook")
        return get_object_or_404(SecurityPolicyRulebook, pk=pk)

    def get(self, request):
        rulebook = self._get_rulebook(request)
        form = RulebookFieldForm()
        from netbox.views.generic.base import BaseObjectView
        from django.template.response import TemplateResponse
        return TemplateResponse(request, "netbox_nsm/rulebookfield_edit.html", {
            "form": form,
            "rulebook": rulebook,
            "object": None,
            "return_url": reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[rulebook.pk]),
        })

    def post(self, request):
        rulebook = self._get_rulebook(request)
        form = RulebookFieldForm(request.POST)
        if form.is_valid():
            field = form.save(commit=False)
            field.rulebook = rulebook
            field.save()
            messages.success(request, _("Field '%(name)s' wurde angelegt.") % {"name": field.name})
            return redirect(reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[rulebook.pk]))
        from django.template.response import TemplateResponse
        return TemplateResponse(request, "netbox_nsm/rulebookfield_edit.html", {
            "form": form,
            "rulebook": rulebook,
            "object": None,
            "return_url": reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[rulebook.pk]),
        })


class RulebookFieldEditView(View):
    """Edit an existing RulebookField."""

    def _get_field(self, pk):
        return get_object_or_404(RulebookField, pk=pk)

    def get(self, request, pk):
        field = self._get_field(pk)
        form = RulebookFieldForm(instance=field)
        from django.template.response import TemplateResponse
        return TemplateResponse(request, "netbox_nsm/rulebookfield_edit.html", {
            "form": form,
            "rulebook": field.rulebook,
            "object": field,
            "return_url": reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[field.rulebook_id]),
        })

    def post(self, request, pk):
        field = self._get_field(pk)
        form = RulebookFieldForm(request.POST, instance=field)
        if form.is_valid():
            field = form.save()
            messages.success(request, _("Field '%(name)s' wurde gespeichert.") % {"name": field.name})
            return redirect(reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[field.rulebook_id]))
        from django.template.response import TemplateResponse
        return TemplateResponse(request, "netbox_nsm/rulebookfield_edit.html", {
            "form": form,
            "rulebook": field.rulebook,
            "object": field,
            "return_url": reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[field.rulebook_id]),
        })


class RulebookFieldDeleteView(View):
    """Delete a RulebookField."""

    def get(self, request, pk):
        field = get_object_or_404(RulebookField, pk=pk)
        from django.template.response import TemplateResponse
        return TemplateResponse(request, "netbox_nsm/rulebookfield_delete.html", {
            "object": field,
            "return_url": reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[field.rulebook_id]),
        })

    def post(self, request, pk):
        field = get_object_or_404(RulebookField, pk=pk)
        rulebook_pk = field.rulebook_id
        field_name = field.name
        field.delete()
        messages.success(request, _("Field '%(name)s' deleted.") % {"name": field_name})
        return redirect(reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[rulebook_pk]))


class RulebookFieldTypeAddView(View):
    """Add a TypeConfig to a RulebookField. ?field=<pk> required."""

    def _get_field(self, request):
        pk = request.GET.get("field") or request.POST.get("field")
        return get_object_or_404(RulebookField, pk=pk)

    def get(self, request):
        field = self._get_field(request)
        form = RulebookFieldTypeForm()
        from django.template.response import TemplateResponse
        return TemplateResponse(request, "netbox_nsm/rulebookfieldtype_edit.html", {
            "form": form,
            "field": field,
            "return_url": reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[field.rulebook_id]),
        })

    def post(self, request):
        field = self._get_field(request)
        form = RulebookFieldTypeForm(request.POST)
        if form.is_valid():
            ft = form.save(commit=False)
            ft.field = field
            ft.save()
            messages.success(request, _("Type added to field '%(name)s'.") % {"name": field.name})
            return redirect(reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[field.rulebook_id]))
        from django.template.response import TemplateResponse
        return TemplateResponse(request, "netbox_nsm/rulebookfieldtype_edit.html", {
            "form": form,
            "field": field,
            "return_url": reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[field.rulebook_id]),
        })


class RulebookFieldTypeEditView(View):
    """Edit an existing RulebookFieldType (e.g. to set max_items)."""

    def get(self, request, pk):
        ft = get_object_or_404(RulebookFieldType, pk=pk)
        form = RulebookFieldTypeForm(instance=ft)
        from django.template.response import TemplateResponse
        return TemplateResponse(request, "netbox_nsm/rulebookfieldtype_edit.html", {
            "form": form,
            "field": ft.field,
            "object": ft,
            "return_url": reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[ft.field.rulebook_id]),
        })

    def post(self, request, pk):
        ft = get_object_or_404(RulebookFieldType, pk=pk)
        form = RulebookFieldTypeForm(request.POST, instance=ft)
        if form.is_valid():
            ft = form.save()
            messages.success(request, _("Field Type '%(name)s' gespeichert.") % {"name": str(ft.type_config)})
            return redirect(reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[ft.field.rulebook_id]))
        from django.template.response import TemplateResponse
        return TemplateResponse(request, "netbox_nsm/rulebookfieldtype_edit.html", {
            "form": form,
            "field": ft.field,
            "object": ft,
            "return_url": reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[ft.field.rulebook_id]),
        })


class RulebookFieldTypeDeleteView(View):
    """Delete a RulebookFieldType entry."""

    def get(self, request, pk):
        ft = get_object_or_404(RulebookFieldType, pk=pk)
        from django.template.response import TemplateResponse
        return TemplateResponse(request, "netbox_nsm/rulebookfieldtype_delete.html", {
            "object": ft,
            "return_url": reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[ft.field.rulebook_id]),
        })

    def post(self, request, pk):
        ft = get_object_or_404(RulebookFieldType, pk=pk)
        rulebook_pk = ft.field.rulebook_id
        ft.delete()
        messages.success(request, _("Type entry deleted."))
        return redirect(reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[rulebook_pk]))
