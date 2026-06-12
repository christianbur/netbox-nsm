"""Views for COT-backed NSM rulebooks."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View

from core.models import ObjectChange
from core.tables import ObjectChangeTable
from utilities.querydict import normalize_querydict

from netbox_nsm.models import CotRulebookAssignment
from netbox_nsm.rulebooks.assigned_objects import build_cot_rulebook_assigned_objects_panel
from netbox_nsm.rulebooks.cot_hierarchy import (
    build_virtual_cot_rulebook_with_hierarchy,
    get_cot_row_group_by_col_id,
)
from netbox_nsm.rulebooks.rules_row_grouping import row_group_column_label_for_cot
from netbox_nsm.rulebooks.create import (
    create_cot_rulebook_from_schema_yaml,
    update_cot_rulebook_metadata,
)
from netbox_nsm.rulebooks.forms.assignment import CotRulebookBulkAssignForm
from netbox_nsm.rulebooks.registry import get_deployed_cot_rulebook
from netbox_nsm.rulebooks.rules_tab import build_cot_rulebook_rules_tab_context
from netbox_nsm.rulebooks.forms.cot import CotRulebookCreateForm, CotRulebookDetailForm
from netbox_nsm.rulebooks.templates import (
    export_rulebook_schema_yaml_for_copy,
    validate_substituted_rulebook_schema_yaml,
    wizard_columns_from_schema_yaml,
)
from netbox_nsm.matrix.cot_matrix_tab_context import (
    build_cot_matrix_tab_context,
    cot_rulebook_matrix_enabled,
)
from netbox_nsm.rulebooks.virtual_cot_tabs import build_virtual_cot_rulebook_tabs

__all__ = (
    "CotRulebookBulkAssignView",
    "CotRulebookChangelogView",
    "CotRulebookCreateView",
    "CotRulebookSchemaValidateView",
    "CotRulebookMatrixView",
    "CotRulebookRulesView",
    "CotRulebookView",
)


class _CotRulebookMixin(LoginRequiredMixin, PermissionRequiredMixin):
    permission_required = "netbox_nsm.view_rulebook"

    def get_virtual_object(self, slug: str):
        cot = get_deployed_cot_rulebook(slug)
        if cot is None:
            from django.http import Http404

            raise Http404()
        return build_virtual_cot_rulebook_with_hierarchy(cot)

    def build_base_context(self, request, slug: str, *, tab_key: str, instance=None):
        if instance is None:
            instance = self.get_virtual_object(slug)
        return {
            "object": instance,
            "tab_key": tab_key,
            "active_tab": tab_key,
            "virtual_rulebook_tabs": build_virtual_cot_rulebook_tabs(
                request,
                instance,
                active_key=tab_key if tab_key != "detail" else None,
            ),
            "actions": [],
            "rulebook_readonly": False,
        }


class CotRulebookView(_CotRulebookMixin, View):
    template_name = "netbox_nsm/rulebook_cot_detail.html"
    tab_key = "detail"

    def _cot_field_groups(self, cot):
        """Group COT fields for the readonly Fields card (custom-objects detail style)."""
        field_groups = {}
        for field in cot.fields.prefetch_related(
            "related_object_type",
            "related_object_types",
        ).order_by("group_name", "weight", "name"):
            group_name = field.group_name or None
            field_groups.setdefault(group_name, []).append(field)
        return field_groups

    def _detail_context(
        self,
        request,
        slug: str,
        *,
        edit_form=None,
        edit_mode=None,
    ):
        instance = self.get_virtual_object(slug)
        cot = instance.cot
        can_edit = request.user.has_perm("netbox_nsm.add_rulebook")
        if edit_mode is None:
            edit_mode = can_edit and request.GET.get("edit") == "1"
        if edit_form is None and edit_mode and can_edit:
            edit_form = CotRulebookDetailForm(cot=cot, rulebook_slug=slug)
        from netbox_nsm.rulebooks.rules_row_grouping import row_group_column_label_for_cot

        row_group_col_id = get_cot_row_group_by_col_id(slug)
        ctx = self.build_base_context(request, slug, tab_key=self.tab_key)
        ctx.update(
            {
                "cot_slug": cot.slug,
                "cot_field_groups": self._cot_field_groups(cot),
                "rules_row_group_column_label": row_group_column_label_for_cot(
                    cot, row_group_col_id
                ),
                "rule_count": instance.rule_count,
                "can_edit": can_edit,
                "edit_mode": bool(edit_mode and can_edit),
                "edit_form": edit_form if can_edit else None,
                "matrix_tab_capable": instance.matrix_tab_capable,
                "assigned_objects_panel": build_cot_rulebook_assigned_objects_panel(
                    cot.slug, request
                ),
                "fields_schema_yaml": export_rulebook_schema_yaml_for_copy(cot),
            }
        )
        return ctx

    def get(self, request, slug: str):
        return render(
            request,
            self.template_name,
            self._detail_context(request, slug),
        )

    def post(self, request, slug: str):
        if not request.user.has_perm("netbox_nsm.add_rulebook"):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied()

        cot = self.get_virtual_object(slug).cot
        form = CotRulebookDetailForm(cot=cot, rulebook_slug=slug, data=request.POST)
        if form.is_valid():
            from netbox_nsm.rulebooks.cot_hierarchy import (
                set_cot_matrix_tab_enabled,
                set_cot_row_group_by_col_id,
                set_cot_rulebook_parent,
            )

            update_cot_rulebook_metadata(
                slug,
                verbose_name=form.cleaned_data["verbose_name"],
                description=form.cleaned_data.get("description") or "",
            )
            set_cot_rulebook_parent(slug, form.cleaned_data.get("parent_slug") or None)
            if "matrix_tab_enabled" in form.cleaned_data:
                set_cot_matrix_tab_enabled(
                    slug,
                    form.cleaned_data["matrix_tab_enabled"],
                )
            set_cot_row_group_by_col_id(
                slug,
                form.cleaned_data.get("row_group_by_col_id") or "",
            )
            messages.success(request, _("Rulebook updated."))
            return redirect(
                reverse(
                    "plugins:netbox_nsm:cot_rulebook",
                    kwargs={"slug": slug},
                )
            )
        return render(
            request,
            self.template_name,
            self._detail_context(request, slug, edit_form=form, edit_mode=True),
        )


class CotRulebookBulkAssignView(_CotRulebookMixin, View):
    """Assign a COT rulebook to multiple devices / VMs / VDCs in one step."""

    permission_required = "netbox_nsm.add_rulebookassignment"
    template_name = "netbox_nsm/cot_rulebook_bulk_assign.html"

    def get(self, request, slug: str):
        instance = self.get_virtual_object(slug)
        ctx = self.build_base_context(request, slug, tab_key="detail")
        ctx.update(
            {
                "form": CotRulebookBulkAssignForm(),
                "assigned_objects_panel": build_cot_rulebook_assigned_objects_panel(
                    slug, request
                ),
            }
        )
        return render(request, self.template_name, ctx)

    def post(self, request, slug: str):
        instance = self.get_virtual_object(slug)
        form = CotRulebookBulkAssignForm(request.POST)
        if form.is_valid():
            created = 0
            skipped = 0
            for device in form.cleaned_data.get("devices") or []:
                ct = ContentType.objects.get_for_model(device)
                _assignment, was_created = CotRulebookAssignment.objects.get_or_create(
                    cot_slug=slug,
                    assigned_object_type=ct,
                    assigned_object_id=device.pk,
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1
            for vm in form.cleaned_data.get("virtual_machines") or []:
                ct = ContentType.objects.get_for_model(vm)
                _assignment, was_created = CotRulebookAssignment.objects.get_or_create(
                    cot_slug=slug,
                    assigned_object_type=ct,
                    assigned_object_id=vm.pk,
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1
            for vdc in form.cleaned_data.get("virtual_device_contexts") or []:
                ct = ContentType.objects.get_for_model(vdc)
                _assignment, was_created = CotRulebookAssignment.objects.get_or_create(
                    cot_slug=slug,
                    assigned_object_type=ct,
                    assigned_object_id=vdc.pk,
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1
            messages.success(
                request,
                _("%(created)d assignment(s) created, %(skipped)d already existed.")
                % {"created": created, "skipped": skipped},
            )
            return redirect(instance.get_absolute_url())
        ctx = self.build_base_context(request, slug, tab_key="detail")
        ctx.update(
            {
                "form": form,
                "assigned_objects_panel": build_cot_rulebook_assigned_objects_panel(
                    slug, request
                ),
            }
        )
        return render(request, self.template_name, ctx)


class CotRulebookRulesView(_CotRulebookMixin, View):
    template_name = "netbox_nsm/rulebook_cot_rules.html"
    tab_key = "rules"

    def get(self, request, slug: str):
        from netbox_nsm.rulebooks.cot_hierarchy import build_virtual_cot_rulebook_with_hierarchy

        cot = get_deployed_cot_rulebook(slug)
        if cot is None:
            from django.http import Http404

            raise Http404()
        instance = build_virtual_cot_rulebook_with_hierarchy(cot, rule_count=0)
        rules_ctx = build_cot_rulebook_rules_tab_context(request, instance)
        if rules_ctx.get("rules_tab_badge") is not None:
            instance.rules_tab_badge = rules_ctx["rules_tab_badge"]
        ctx = self.build_base_context(
            request, slug, tab_key=self.tab_key, instance=instance
        )
        ctx.update(rules_ctx)
        return render(request, self.template_name, ctx)


class CotRulebookMatrixView(_CotRulebookMixin, View):
    template_name = "netbox_nsm/rulebook_cot_matrix.html"
    tab_key = "matrix"

    def get(self, request, slug: str):
        instance = self.get_virtual_object(slug)
        if not cot_rulebook_matrix_enabled(instance.cot):
            from django.http import Http404

            raise Http404()
        ctx = self.build_base_context(request, slug, tab_key=self.tab_key)
        ctx.update(build_cot_matrix_tab_context(request, instance))
        return render(request, self.template_name, ctx)


class CotRulebookChangelogView(_CotRulebookMixin, View):
    permission_required = "core.view_objectchange"
    template_name = "netbox_nsm/rulebook_cot_changelog.html"
    tab_key = "changelog"

    def get(self, request, slug: str):
        instance = self.get_virtual_object(slug)
        cot = instance.cot
        content_type = ContentType.objects.get_for_model(cot)
        objectchanges = (
            ObjectChange.objects.restrict(request.user, "view")
            .prefetch_related("user", "changed_object_type")
            .filter(
                Q(changed_object_type=content_type, changed_object_id=cot.pk)
                | Q(related_object_type=content_type, related_object_id=cot.pk)
            )
        )
        table = ObjectChangeTable(data=objectchanges, orderable=False)
        table.configure(request)
        ctx = self.build_base_context(request, slug, tab_key=self.tab_key)
        ctx.update(
            {
                "table": table,
                "feature_tab_label": _("Changelog"),
            }
        )
        return render(request, self.template_name, ctx)


class CotRulebookSchemaValidateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "netbox_nsm.add_rulebook"

    def post(self, request):
        schema_yaml = request.POST.get("schema_yaml", "")
        try:
            validate_substituted_rulebook_schema_yaml(
                schema_yaml,
                display_name=request.POST.get("verbose_name", ""),
                name=request.POST.get("name", ""),
                description=request.POST.get("description", ""),
            )
        except ValidationError as exc:
            message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
            return JsonResponse({"valid": False, "error": str(message)})
        except Exception as exc:
            return JsonResponse({"valid": False, "error": str(exc)})
        return JsonResponse({"valid": True})


class CotRulebookCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "netbox_nsm.add_rulebook"
    template_name = "netbox_nsm/cot_rulebook_create.html"

    def get(self, request):
        initial_data = normalize_querydict(request.GET)
        form = CotRulebookCreateForm(initial=initial_data)
        return render(
            request,
            self.template_name,
            self._context(request, form),
        )

    def post(self, request):
        form = CotRulebookCreateForm(request.POST)
        if form.is_valid():
            try:
                cot = create_cot_rulebook_from_schema_yaml(
                    schema_yaml=form.cleaned_data["schema_yaml"],
                    name=form.cleaned_data["name"],
                    verbose_name=form.cleaned_data.get("verbose_name") or None,
                    description=form.cleaned_data.get("description") or None,
                    parent_slug=form.cleaned_data.get("parent_slug") or None,
                )
            except Exception as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(
                    request,
                    _("Rulebook %(name)s created.") % {"name": cot.verbose_name},
                )
                return redirect(
                    reverse(
                        "plugins:netbox_nsm:cot_rulebook",
                        kwargs={"slug": cot.slug},
                    )
                )
        return render(
            request,
            self.template_name,
            self._context(request, form),
        )

    def _context(self, request, form) -> dict:
        from netbox_nsm.rulebooks.create import resolve_rulebook_slug
        from netbox_nsm.rulebooks.templates import (
            default_rulebook_schema_yaml,
            substitute_rulebook_schema_placeholders,
        )

        from netbox_nsm.rulebooks.create import derive_rulebook_name

        preview_slug = ""
        if form.is_bound and not form.errors.get("verbose_name"):
            try:
                raw_name = (form.data.get("name") or "").strip()
                if not raw_name:
                    raw_name = derive_rulebook_name(form.data.get("verbose_name", ""))
                preview_slug = resolve_rulebook_slug(raw_name)
            except Exception:
                preview_slug = ""

        schema_yaml = (
            form.data.get("schema_yaml")
            if form.is_bound
            else form.initial.get("schema_yaml") or default_rulebook_schema_yaml()
        )
        preview_display = (
            (form.data.get("verbose_name") or "").strip() if form.is_bound else ""
        )
        preview_name = (form.data.get("name") or "").strip() if form.is_bound else ""
        if form.is_bound and not preview_name and preview_display:
            preview_name = derive_rulebook_name(preview_display)
        preview_description = (
            (form.data.get("description") or "").strip() if form.is_bound else ""
        )
        resolved_schema_yaml = substitute_rulebook_schema_placeholders(
            schema_yaml,
            display_name=preview_display,
            name=preview_name,
            description=preview_description,
        )
        columns = []
        schema_error = None
        try:
            columns = wizard_columns_from_schema_yaml(resolved_schema_yaml)
        except Exception as exc:
            schema_error = str(exc)

        return {
            "form": form,
            "template_columns": columns,
            "schema_error": schema_error,
            "preview_slug": preview_slug,
        }
