"""Security-menu routes for NSM Custom Object CRUD (wraps netbox-custom-objects)."""

from __future__ import annotations

from django.http import Http404

from netbox_nsm.objects.cot_routes import (
    is_nsm_object_menu_slug,
    nsm_object_reverse,
    reset_current_nsm_object_route_slug,
    set_current_nsm_object_route_slug,
)
from netbox_nsm.views.cot_list_table import (
    CotPolymorphicListTableMixin,
    _non_sortable_polymorphic_object_fields,
    _request_without_sort_on_blocked_fields,
    _strip_blocked_ordering,
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

    class NsmCustomObjectListView(
        NsmObjectRouteMixin,
        CotPolymorphicListTableMixin,
        CustomObjectListView,
    ):
        pass

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
