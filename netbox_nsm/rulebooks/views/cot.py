"""Views for COT-backed NSM rulebooks."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View

from core.models import ObjectChange
from core.tables import ObjectChangeTable
from utilities.htmx import htmx_partial
from utilities.querydict import normalize_querydict

from netbox_nsm.models import CotRulebookAssignment
from netbox_nsm.rulebooks.assigned_objects import build_cot_rulebook_assigned_objects_panel
from netbox_nsm.rulebooks.cot_hierarchy import build_virtual_cot_rulebook_with_hierarchy
from netbox_nsm.rulebooks.create import (
    create_cot_rulebook_from_template,
    update_cot_rulebook_metadata,
)
from netbox_nsm.rulebooks.forms.assignment import CotRulebookBulkAssignForm
from netbox_nsm.rulebooks.registry import get_deployed_cot_rulebook
from netbox_nsm.rulebooks.rules_tab import build_cot_rulebook_rules_tab_context
from netbox_nsm.rulebooks.forms.cot import CotRulebookCreateForm, CotRulebookDetailForm
from netbox_nsm.rulebooks.templates import template_wizard_columns
from netbox_nsm.matrix.cot_matrix_tab_context import (
    build_cot_matrix_tab_context,
    cot_rulebook_matrix_enabled,
)
from netbox_nsm.rulebooks.virtual_cot_tabs import build_virtual_cot_rulebook_tabs

__all__ = (
    "CotRulebookBulkAssignView",
    "CotRulebookChangelogView",
    "CotRulebookCreateView",
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
        ctx = self.build_base_context(request, slug, tab_key=self.tab_key)
        ctx.update(
            {
                "cot_slug": cot.slug,
                "cot_field_groups": self._cot_field_groups(cot),
                "rule_count": instance.rule_count,
                "can_edit": can_edit,
                "edit_mode": bool(edit_mode and can_edit),
                "edit_form": edit_form if can_edit else None,
                "matrix_tab_capable": instance.matrix_tab_capable,
                "assigned_objects_panel": build_cot_rulebook_assigned_objects_panel(
                    cot.slug, request
                ),
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
        total_rules = rules_ctx.get("rules_total_rules")
        if total_rules is not None:
            instance.rule_count = total_rules
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


class CotRulebookCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "netbox_nsm.add_rulebook"
    template_name = "netbox_nsm/cot_rulebook_create.html"
    htmx_template_name = "netbox_nsm/htmx/cot_rulebook_create_fields.html"

    def get(self, request):
        from netbox_nsm.views.setup.demo import _ensure_rulebook_templates

        _ensure_rulebook_templates()
        initial_data = normalize_querydict(request.GET)
        form = CotRulebookCreateForm(initial=initial_data)
        template_slug = self._resolve_template_slug(form, initial_data)
        context = self._context(request, form, template_slug)

        if htmx_partial(request):
            return render(request, self.htmx_template_name, context)

        return render(request, self.template_name, context)

    def post(self, request):
        from netbox_nsm.views.setup.demo import _ensure_rulebook_templates

        _ensure_rulebook_templates()
        form = CotRulebookCreateForm(request.POST)
        template_slug = request.POST.get("template_slug") or ""
        if form.is_valid():
            try:
                cot = create_cot_rulebook_from_template(
                    template_slug=form.cleaned_data["template_slug"],
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
            self._context(request, form, template_slug),
        )

    @staticmethod
    def _resolve_template_slug(form, data: dict) -> str:
        template_slug = (data.get("template_slug") or "").strip()
        if template_slug:
            return template_slug
        choices = form.fields["template_slug"].choices
        if choices:
            return choices[0][0]
        return ""

    def _context(self, request, form, template_slug: str) -> dict:
        from netbox_nsm.rulebooks.create import resolve_rulebook_slug

        preview_slug = ""
        if form.is_bound and not form.errors.get("name"):
            try:
                preview_slug = resolve_rulebook_slug(form.data.get("name", ""))
            except Exception:
                preview_slug = ""
        columns = template_wizard_columns(template_slug) if template_slug else []
        return {
            "form": form,
            "template_slug": template_slug,
            "template_columns": columns,
            "preview_slug": preview_slug,
        }
