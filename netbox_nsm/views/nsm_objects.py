"""Security-menu routes for NSM Custom Object CRUD (wraps netbox-custom-objects)."""

from __future__ import annotations

from django.http import Http404

from netbox_nsm.objects.cot_routes import (
    is_nsm_object_menu_slug,
    nsm_object_reverse,
    reset_current_nsm_object_route_slug,
    set_current_nsm_object_route_slug,
)

__all__ = (
    "NsmCustomObjectBulkDeleteView",
    "NsmCustomObjectBulkEditView",
    "NsmCustomObjectBulkImportView",
    "NsmCustomObjectChangeLogView",
    "NsmCustomObjectDeleteView",
    "NsmCustomObjectEditView",
    "NsmCustomObjectJournalView",
    "NsmCustomObjectListView",
    "NsmCustomObjectView",
)


class NsmObjectRouteMixin:
    """Only allow built-in NSM object slugs and keep URL helpers scoped."""

    def dispatch(self, request, *args, **kwargs):
        slug = kwargs.get("custom_object_type")
        if not is_nsm_object_menu_slug(slug):
            raise Http404
        token = set_current_nsm_object_route_slug(slug)
        try:
            return super().dispatch(request, *args, **kwargs)
        finally:
            reset_current_nsm_object_route_slug(token)


def _non_sortable_polymorphic_object_fields(cot) -> frozenset[str]:
    """Polymorphic GFK columns cannot be used in SQL ``ORDER BY``."""
    if cot is None:
        return frozenset()
    from extras.choices import CustomFieldTypeChoices

    return frozenset(
        cot.fields.filter(
            type=CustomFieldTypeChoices.TYPE_OBJECT,
            is_polymorphic=True,
        ).values_list("name", flat=True)
    )


def _strip_blocked_ordering(ordering, blocked: frozenset[str]):
    if not ordering or not blocked:
        return ordering
    cleaned = tuple(o for o in ordering if o.lstrip("-") not in blocked)
    return cleaned


def _request_without_sort_on_blocked_fields(request, blocked: frozenset[str]):
    sort = request.GET.get("sort", "")
    if not sort or sort.lstrip("-") not in blocked:
        return request
    params = request.GET.copy()
    params.pop("sort", None)
    request.GET = params
    return request


try:
    from netbox_custom_objects.views import (
        CustomObjectBulkDeleteView,
        CustomObjectBulkEditView,
        CustomObjectBulkImportView,
        CustomObjectChangeLogView,
        CustomObjectDeleteView,
        CustomObjectEditView,
        CustomObjectJournalView,
        CustomObjectListView,
        CustomObjectView,
    )

    class NsmCustomObjectListView(NsmObjectRouteMixin, CustomObjectListView):
        def _prepare_list_table_request(self, request):
            """Drop invalid sort params before django-tables2 configures ordering."""
            cot = getattr(self, "custom_object_type", None)
            blocked = _non_sortable_polymorphic_object_fields(cot)
            if not blocked:
                return request

            request = _request_without_sort_on_blocked_fields(request, blocked)

            if request.user.is_authenticated and cot is not None:
                model = cot.get_model()
                table_name = f"{model._meta.object_name}Table"
                config_key = f"tables.{table_name}.ordering"
                ordering = request.user.config.get(config_key)
                cleaned = _strip_blocked_ordering(ordering, blocked)
                if cleaned != ordering:
                    request.user.config.set(config_key, list(cleaned), commit=True)
            return request

        def get_table(self, data, request, bulk_actions=True):
            request = self._prepare_list_table_request(request)
            table = super().get_table(data, request, bulk_actions=bulk_actions)
            blocked = _non_sortable_polymorphic_object_fields(
                getattr(self, "custom_object_type", None)
            )
            for name in blocked:
                if name in table.base_columns:
                    table.base_columns[name].orderable = False
            if table.order_by:
                table.order_by = _strip_blocked_ordering(table.order_by, blocked)
            return table

    class NsmCustomObjectView(NsmObjectRouteMixin, CustomObjectView):
        template_name = "netbox_nsm/customobject.html"

    class NsmCustomObjectEditView(NsmObjectRouteMixin, CustomObjectEditView):
        pass

    class NsmCustomObjectDeleteView(NsmObjectRouteMixin, CustomObjectDeleteView):
        default_return_url = "plugins:netbox_nsm:nsm_object_list"

        def get_return_url(self, request, obj=None):
            if obj:
                slug = obj.custom_object_type.slug
            else:
                slug = self.kwargs.get("custom_object_type")
            return nsm_object_reverse("list", slug)

    class NsmCustomObjectBulkEditView(NsmObjectRouteMixin, CustomObjectBulkEditView):
        pass

    class NsmCustomObjectBulkDeleteView(NsmObjectRouteMixin, CustomObjectBulkDeleteView):
        pass

    class NsmCustomObjectBulkImportView(NsmObjectRouteMixin, CustomObjectBulkImportView):
        pass

    class NsmCustomObjectJournalView(NsmObjectRouteMixin, CustomObjectJournalView):
        base_template = "netbox_nsm/customobject.html"

    class NsmCustomObjectChangeLogView(NsmObjectRouteMixin, CustomObjectChangeLogView):
        base_template = "netbox_nsm/customobject.html"

except ImportError:
    from django.views import View

    class _UnavailableNsmObjectView(View):
        def dispatch(self, request, *args, **kwargs):
            raise Http404

    NsmCustomObjectListView = _UnavailableNsmObjectView
    NsmCustomObjectView = _UnavailableNsmObjectView
    NsmCustomObjectEditView = _UnavailableNsmObjectView
    NsmCustomObjectDeleteView = _UnavailableNsmObjectView
    NsmCustomObjectBulkEditView = _UnavailableNsmObjectView
    NsmCustomObjectBulkDeleteView = _UnavailableNsmObjectView
    NsmCustomObjectBulkImportView = _UnavailableNsmObjectView
    NsmCustomObjectJournalView = _UnavailableNsmObjectView
    NsmCustomObjectChangeLogView = _UnavailableNsmObjectView
