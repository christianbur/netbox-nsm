"""Views for COT-backed NSM rulebooks."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
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

from netbox_nsm.rulebooks.assigned_objects import build_cot_rulebook_assigned_objects_panel
from netbox_nsm.rulebooks.cot_hierarchy import (
    build_virtual_cot_rulebook_with_hierarchy,
    get_cot_row_group_by_col_id,
)
from netbox_nsm.rulebooks.rules_row_grouping import row_group_column_label_for_cot
from netbox_nsm.rulebooks.create import (
    build_rulebook_clone_form_initial,
    create_cot_rulebook_from_schema_yaml,
    iter_deployed_rulebook_clone_choices,
    update_cot_rulebook_metadata,
)
from netbox_nsm.rulebooks.forms.bulk_assign import CotRulebookBulkAssignForm
from netbox_nsm.rulebooks.registry import get_deployed_cot_rulebook
from netbox_nsm.rulebooks.rules_tab import build_cot_rulebook_rules_tab_context
from netbox_nsm.rulebooks.forms.cot import CotRulebookCreateForm, CotRulebookDetailForm
from netbox_nsm.rulebooks.templates import (
    validate_substituted_rulebook_schema_yaml,
    wizard_columns_from_schema_yaml,
)
from netbox_nsm.rulebooks.matrix.cot_matrix_tab_context import (
    build_cot_matrix_tab_context,
    cot_rulebook_matrix_enabled,
)
from netbox_nsm.rulebooks.delete_blockers import deployed_rulebook_delete_blockers
from netbox_nsm.rulebooks.permissions import (
    can_change_rulebook,
    can_create_rulebook,
    can_show_rulebook_delete,
    can_view_rulebook,
)
from netbox_nsm.rulebooks.virtual_cot_tabs import build_virtual_cot_rulebook_tabs

__all__ = (
    "CotRulebookBulkAssignView",
    "CotRulebookChangelogView",
    "CotRulebookCreateView",
    "CotRulebookSchemaValidateView",
    "CotRulebookDeleteView",
    "CotRulebookMatrixView",
    "CotRulebookRulesView",
    "CotRulebookView",
)


class _CotRulebookMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        slug = kwargs.get("slug")
        if slug:
            cot = get_deployed_cot_rulebook(slug)
            if cot is None:
                from django.http import Http404

                raise Http404()
            if not can_view_rulebook(request.user, cot):
                raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

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
        can_edit = can_change_rulebook(request.user, cot)
        if edit_mode is None:
            edit_mode = can_edit and request.GET.get("edit") == "1"
        if edit_form is None and edit_mode and can_edit:
            edit_form = CotRulebookDetailForm(cot=cot, rulebook_slug=slug)
        from netbox_nsm.rulebooks.rules_row_grouping import row_group_column_label_for_cot

        row_group_col_id = get_cot_row_group_by_col_id(slug)
        rule_count = instance.rule_count
        can_show_delete = can_show_rulebook_delete(request.user)
        rulebook_edit_url = reverse(
            "plugins:netbox_nsm:cot_rulebook",
            kwargs={"slug": slug},
        )
        if can_edit:
            rulebook_edit_url = f"{rulebook_edit_url}?edit=1"
        rulebook_delete_url = ""
        if can_show_delete:
            rulebook_delete_url = reverse(
                "plugins:netbox_nsm:cot_rulebook_delete",
                kwargs={"slug": slug},
            )
        ctx = self.build_base_context(request, slug, tab_key=self.tab_key)
        ctx.update(
            {
                "cot_slug": cot.slug,
                "rules_row_group_column_label": row_group_column_label_for_cot(
                    cot, row_group_col_id
                ),
                "rule_count": rule_count,
                "can_edit": can_edit,
                "can_show_delete": can_show_delete,
                "edit_mode": bool(edit_mode and can_edit),
                "edit_form": edit_form if can_edit else None,
                "rulebook_edit_url": rulebook_edit_url,
                "rulebook_delete_url": rulebook_delete_url,
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
        cot = self.get_virtual_object(slug).cot
        if not can_change_rulebook(request.user, cot):
            raise PermissionDenied()
        form = CotRulebookDetailForm(cot=cot, rulebook_slug=slug, data=request.POST)
        if form.is_valid():
            from netbox_nsm.type_metadata.rulebook import save_rulebook_config_for_cot

            update_cot_rulebook_metadata(
                slug,
                verbose_name=form.cleaned_data["verbose_name"],
                description=form.cleaned_data.get("description") or "",
            )
            rulebook_config = {
                "parent_slug": form.cleaned_data.get("parent_slug") or "",
                "row_group_by_col_id": form.cleaned_data.get("row_group_by_col_id") or "",
            }
            if "matrix_tab_enabled" in form.cleaned_data:
                rulebook_config["matrix_tab_enabled"] = form.cleaned_data[
                    "matrix_tab_enabled"
                ]
            save_rulebook_config_for_cot(cot, rulebook_config)
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


class CotRulebookDeleteView(_CotRulebookMixin, View):
    template_name = "netbox_nsm/rulebook_cot_delete.html"

    def _context(self, request, slug: str):
        instance = self.get_virtual_object(slug)
        cot = instance.cot
        if not can_show_rulebook_delete(request.user):
            raise PermissionDenied()
        return_url = reverse(
            "plugins:netbox_nsm:cot_rulebook",
            kwargs={"slug": slug},
        )
        blockers = deployed_rulebook_delete_blockers(
            cot,
            rule_count=instance.rule_count,
        )
        return {
            "object": instance,
            "cot": cot,
            "blockers": blockers,
            "return_url": return_url,
            "can_delete": not blockers,
        }

    def get(self, request, slug: str):
        return render(request, self.template_name, self._context(request, slug))

    def post(self, request, slug: str):
        ctx = self._context(request, slug)
        if not ctx["can_delete"]:
            messages.error(
                request,
                _("This rulebook cannot be deleted yet."),
            )
            return render(request, self.template_name, ctx)
        ctx["cot"].delete()
        messages.success(
            request,
            _("Rulebook %(name)s deleted.") % {"name": ctx["object"].name},
        )
        return redirect(reverse("plugins:netbox_nsm:rulebook_list"))


class CotRulebookBulkAssignView(_CotRulebookMixin, View):
    """Assign a COT rulebook to multiple devices / VMs / VDCs in one step."""

    template_name = "netbox_nsm/cot_rulebook_bulk_assign.html"

    def get_permission_required(self):
        from netbox_nsm.security.links.object_link_service import object_link_permission

        return object_link_permission("add") or "netbox_custom_objects.add_customobject"

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
            from netbox_nsm.security.links.object_link_service import create_or_update_enforcement_point_link

            created = 0
            skipped = 0
            for device in form.cleaned_data.get("devices") or []:
                _link, was_created = create_or_update_enforcement_point_link(device, slug)
                if was_created:
                    created += 1
                else:
                    skipped += 1
            for vm in form.cleaned_data.get("virtual_machines") or []:
                _link, was_created = create_or_update_enforcement_point_link(vm, slug)
                if was_created:
                    created += 1
                else:
                    skipped += 1
            for vdc in form.cleaned_data.get("virtual_device_contexts") or []:
                _link, was_created = create_or_update_enforcement_point_link(vdc, slug)
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
    template_name = "netbox_nsm/rulebook_cot_changelog.html"
    tab_key = "changelog"

    def get(self, request, slug: str):
        if not request.user.has_perm("core.view_objectchange"):
            raise PermissionDenied()
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


class CotRulebookSchemaValidateView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not can_create_rulebook(request.user):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

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


class CotRulebookCreateView(LoginRequiredMixin, View):
    template_name = "netbox_nsm/cot_rulebook_create.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not can_create_rulebook(request.user):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        clone_from = (request.GET.get("clone_from") or "").strip()
        initial: dict = {}
        if clone_from:
            cot = get_deployed_cot_rulebook(clone_from)
            if cot is not None and can_view_rulebook(request.user, cot):
                initial = build_rulebook_clone_form_initial(cot)
        form = CotRulebookCreateForm(initial=initial)
        return render(
            request,
            self.template_name,
            self._context(request, form, clone_from=clone_from),
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

    def _context(self, request, form, *, clone_from: str = "") -> dict:
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
            "clone_from": clone_from,
            "clone_choices": iter_deployed_rulebook_clone_choices(request.user),
        }
