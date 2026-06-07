from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic.edit import FormView

from utilities.views import register_model_view

from netbox_nsm.forms.rulebook_field import RulebookFieldForm, RulebookFieldTypeForm
from netbox_nsm.models import RulebookField, RulebookFieldType, Rulebook, TypeConfig
from netbox_nsm.changelog_utils import (
    record_rulebook_layout_changelog,
    snapshot_instance,
)

__all__ = (
    "RulebookFieldAddView",
    "RulebookFieldEditView",
    "RulebookFieldDeleteView",
    "RulebookFieldTypeAddView",
    "RulebookFieldTypeEditView",
    "RulebookFieldTypeDeleteView",
)


def _log_rulebook_fields_change(rulebook, request, *, message=""):
    prechange = getattr(request, "_nsm_rulebook_fields_prechange", None)
    if prechange is None:
        return
    record_rulebook_layout_changelog(rulebook, request, prechange, message=message)


def _begin_rulebook_fields_change(rulebook, request):
    request._nsm_rulebook_fields_prechange = snapshot_instance(rulebook, fields_layout=True)


class RulebookFieldAddView(View):
    """Add a RulebookField to a Rulebook. ?rulebook=<pk> required."""

    def _get_rulebook(self, request):
        pk = request.GET.get("rulebook") or request.POST.get("rulebook")
        return get_object_or_404(Rulebook, pk=pk)

    def get(self, request):
        rulebook = self._get_rulebook(request)
        form = RulebookFieldForm()
        from netbox.views.generic.base import BaseObjectView
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "netbox_nsm/rulebookfield_edit.html",
            {
                "form": form,
                "rulebook": rulebook,
                "object": None,
                "return_url": reverse(
                    "plugins:netbox_nsm:rulebook", args=[rulebook.pk]
                ),
            },
        )

    def post(self, request):
        rulebook = self._get_rulebook(request)
        form = RulebookFieldForm(request.POST)
        if form.is_valid():
            _begin_rulebook_fields_change(rulebook, request)
            field = form.save(commit=False)
            field.rulebook = rulebook
            field.save()
            if "type_configs" in form.fields:
                selected = set(form.cleaned_data.get("type_configs") or [])
                max_items = form.cleaned_data.get("max_items")
                for tc in selected:
                    RulebookFieldType.objects.get_or_create(
                        field=field,
                        type_config=tc,
                        defaults={"max_items": max_items},
                    )
            _log_rulebook_fields_change(rulebook, request)
            messages.success(
                request, _("Field '%(name)s' was created.") % {"name": field.name}
            )
            return redirect(reverse("plugins:netbox_nsm:rulebook", args=[rulebook.pk]))
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "netbox_nsm/rulebookfield_edit.html",
            {
                "form": form,
                "rulebook": rulebook,
                "object": None,
                "return_url": reverse(
                    "plugins:netbox_nsm:rulebook", args=[rulebook.pk]
                ),
            },
        )


class RulebookFieldEditView(View):
    """Edit an existing RulebookField."""

    def _get_field(self, pk):
        return get_object_or_404(RulebookField, pk=pk)

    def get(self, request, pk):
        field = self._get_field(pk)
        form = RulebookFieldForm(instance=field)
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "netbox_nsm/rulebookfield_edit.html",
            {
                "form": form,
                "rulebook": field.rulebook,
                "object": field,
                "return_url": reverse(
                    "plugins:netbox_nsm:rulebook",
                    args=[field.rulebook_id],
                ),
            },
        )

    def post(self, request, pk):
        field = self._get_field(pk)
        form = RulebookFieldForm(request.POST, instance=field)
        if form.is_valid():
            rulebook = field.rulebook
            _begin_rulebook_fields_change(rulebook, request)
            field = form.save()
            if "type_configs" in form.fields:
                selected = set(form.cleaned_data.get("type_configs") or [])
                max_items = form.cleaned_data.get("max_items")
                existing_map = {
                    ft.type_config: ft
                    for ft in RulebookFieldType.objects.filter(field=field)
                }
                for tc in selected:
                    if tc not in existing_map:
                        RulebookFieldType.objects.create(
                            field=field, type_config=tc, max_items=max_items
                        )
                    elif existing_map[tc].max_items != max_items:
                        existing_map[tc].max_items = max_items
                        existing_map[tc].save(update_fields=["max_items"])
                for tc, ft in existing_map.items():
                    if tc not in selected:
                        ft.delete()
            _log_rulebook_fields_change(rulebook, request)
            messages.success(
                request, _("Field '%(name)s' was saved.") % {"name": field.name}
            )
            return redirect(
                reverse(
                    "plugins:netbox_nsm:rulebook",
                    args=[field.rulebook_id],
                )
            )
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "netbox_nsm/rulebookfield_edit.html",
            {
                "form": form,
                "rulebook": field.rulebook,
                "object": field,
                "return_url": reverse(
                    "plugins:netbox_nsm:rulebook",
                    args=[field.rulebook_id],
                ),
            },
        )


class RulebookFieldDeleteView(View):
    """Delete a RulebookField."""

    def get(self, request, pk):
        field = get_object_or_404(RulebookField, pk=pk)
        if field.is_system_field:
            messages.error(request, _("System fields cannot be deleted."))
            return redirect(
                reverse(
                    "plugins:netbox_nsm:rulebook",
                    args=[field.rulebook_id],
                )
            )
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "netbox_nsm/rulebookfield_delete.html",
            {
                "object": field,
                "return_url": reverse(
                    "plugins:netbox_nsm:rulebook",
                    args=[field.rulebook_id],
                ),
            },
        )

    def post(self, request, pk):
        field = get_object_or_404(RulebookField, pk=pk)
        if field.is_system_field:
            messages.error(request, _("System fields cannot be deleted."))
            return redirect(
                reverse(
                    "plugins:netbox_nsm:rulebook",
                    args=[field.rulebook_id],
                )
            )
        rulebook = field.rulebook
        rulebook_pk = field.rulebook_id
        field_name = field.name
        _begin_rulebook_fields_change(rulebook, request)
        field.delete()
        _log_rulebook_fields_change(rulebook, request)
        messages.success(request, _("Field '%(name)s' deleted.") % {"name": field_name})
        return redirect(reverse("plugins:netbox_nsm:rulebook", args=[rulebook_pk]))


class RulebookFieldTypeAddView(View):
    """Add a TypeConfig to a RulebookField. ?field=<pk> required."""

    def _get_field(self, request):
        pk = request.GET.get("field") or request.POST.get("field")
        return get_object_or_404(RulebookField, pk=pk)

    def get(self, request):
        field = self._get_field(request)
        if field.is_system_field:
            messages.error(request, _("Types cannot be added to system fields."))
            return redirect(
                reverse(
                    "plugins:netbox_nsm:rulebook",
                    args=[field.rulebook_id],
                )
            )
        form = RulebookFieldTypeForm()
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "netbox_nsm/rulebookfieldtype_edit.html",
            {
                "form": form,
                "field": field,
                "return_url": reverse(
                    "plugins:netbox_nsm:rulebook",
                    args=[field.rulebook_id],
                ),
            },
        )

    def post(self, request):
        field = self._get_field(request)
        form = RulebookFieldTypeForm(request.POST)
        if form.is_valid():
            rulebook = field.rulebook
            _begin_rulebook_fields_change(rulebook, request)
            ft = form.save(commit=False)
            ft.field = field
            ft.save()
            _log_rulebook_fields_change(rulebook, request)
            messages.success(
                request, _("Type added to field '%(name)s'.") % {"name": field.name}
            )
            return redirect(
                reverse(
                    "plugins:netbox_nsm:rulebook",
                    args=[field.rulebook_id],
                )
            )
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "netbox_nsm/rulebookfieldtype_edit.html",
            {
                "form": form,
                "field": field,
                "return_url": reverse(
                    "plugins:netbox_nsm:rulebook",
                    args=[field.rulebook_id],
                ),
            },
        )


class RulebookFieldTypeEditView(View):
    """Edit an existing RulebookFieldType (e.g. to set max_items)."""

    def get(self, request, pk):
        ft = get_object_or_404(RulebookFieldType, pk=pk)
        form = RulebookFieldTypeForm(instance=ft)
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "netbox_nsm/rulebookfieldtype_edit.html",
            {
                "form": form,
                "field": ft.field,
                "object": ft,
                "return_url": reverse(
                    "plugins:netbox_nsm:rulebook",
                    args=[ft.field.rulebook_id],
                ),
            },
        )

    def post(self, request, pk):
        ft = get_object_or_404(RulebookFieldType, pk=pk)
        form = RulebookFieldTypeForm(request.POST, instance=ft)
        if form.is_valid():
            rulebook = ft.field.rulebook
            _begin_rulebook_fields_change(rulebook, request)
            ft = form.save()
            _log_rulebook_fields_change(rulebook, request)
            messages.success(
                request,
                _("Field type '%(name)s' was saved.") % {"name": str(ft.type_config)},
            )
            return redirect(
                reverse(
                    "plugins:netbox_nsm:rulebook",
                    args=[ft.field.rulebook_id],
                )
            )
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "netbox_nsm/rulebookfieldtype_edit.html",
            {
                "form": form,
                "field": ft.field,
                "object": ft,
                "return_url": reverse(
                    "plugins:netbox_nsm:rulebook",
                    args=[ft.field.rulebook_id],
                ),
            },
        )


class RulebookFieldTypeDeleteView(View):
    """Delete a RulebookFieldType entry."""

    def get(self, request, pk):
        ft = get_object_or_404(RulebookFieldType, pk=pk)
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "netbox_nsm/rulebookfieldtype_delete.html",
            {
                "object": ft,
                "return_url": reverse(
                    "plugins:netbox_nsm:rulebook",
                    args=[ft.field.rulebook_id],
                ),
            },
        )

    def post(self, request, pk):
        ft = get_object_or_404(RulebookFieldType, pk=pk)
        rulebook = ft.field.rulebook
        rulebook_pk = ft.field.rulebook_id
        _begin_rulebook_fields_change(rulebook, request)
        ft.delete()
        _log_rulebook_fields_change(rulebook, request)
        messages.success(request, _("Type entry deleted."))
        return redirect(reverse("plugins:netbox_nsm:rulebook", args=[rulebook_pk]))
