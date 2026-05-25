from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from netbox.views import generic
from utilities.views import register_model_view

from netbox_nsm.filtersets import ObjectGroupFilterSet
from netbox_nsm.forms import ObjectGroupForm, ObjectGroupFilterForm, ObjectGroupBulkEditForm
from netbox_nsm.models import ObjectGroup
from netbox_nsm.tables import ObjectGroupTable

__all__ = (
    "ObjectGroupView",
    "ObjectGroupListView",
    "ObjectGroupEditView",
    "ObjectGroupDeleteView",
    "ObjectGroupBulkEditView",
    "ObjectGroupBulkDeleteView",
    "ObjectGroupAreaView",
)

_MAIN_TABS = (
    {"slug": "srcdst",   "label": "Source/Destination", "href": "/plugins/netbox-nsm/object/"},
    {"slug": "services", "label": "Services",           "href": "/plugins/netbox-nsm/object/"},
    {"slug": "action",   "label": "Action",             "href": "/plugins/netbox-nsm/object/"},
    {"slug": "info",     "label": "Info",               "href": "/plugins/netbox-nsm/object/"},
    {"slug": "groups",   "label": "Groups",             "href": "/plugins/netbox-nsm/object/groups/"},
    {"slug": "custom",   "label": "Object-Builder",     "href": "/plugins/netbox-nsm/object/custom/"},
)

_AREA_TABS = (
    {"slug": "srcdst",   "label": _("Source/Destination"), "href": "/plugins/netbox-nsm/object/groups/srcdst/"},
    {"slug": "services", "label": _("Services"),           "href": "/plugins/netbox-nsm/object/groups/services/"},
    {"slug": "action",   "label": _("Action"),             "href": "/plugins/netbox-nsm/object/groups/action/"},
)


@register_model_view(ObjectGroup)
class ObjectGroupView(generic.ObjectView):
    queryset = ObjectGroup.objects.prefetch_related("members__custom_type", "sub_groups", "tags")
    template_name = "netbox_nsm/objectgroup.html"

    def get_extra_context(self, request, instance):
        return {
            "members": instance.members.select_related("custom_type").order_by(
                "custom_type__name", "name"
            ),
            "sub_groups": instance.sub_groups.order_by("name"),
        }


@register_model_view(ObjectGroup, "list", path="", detail=False)
class ObjectGroupListView(generic.ObjectListView):
    queryset = ObjectGroup.objects.prefetch_related("members", "sub_groups", "tags")
    filterset = ObjectGroupFilterSet
    filterset_form = ObjectGroupFilterForm
    table = ObjectGroupTable


@register_model_view(ObjectGroup, "add", detail=False)
@register_model_view(ObjectGroup, "edit")
class ObjectGroupEditView(generic.ObjectEditView):
    queryset = ObjectGroup.objects.all()
    form = ObjectGroupForm


@register_model_view(ObjectGroup, "delete")
class ObjectGroupDeleteView(generic.ObjectDeleteView):
    queryset = ObjectGroup.objects.all()


@register_model_view(ObjectGroup, "bulk_edit", path="edit", detail=False)
class ObjectGroupBulkEditView(generic.BulkEditView):
    queryset = ObjectGroup.objects.all()
    filterset = ObjectGroupFilterSet
    table = ObjectGroupTable
    form = ObjectGroupBulkEditForm


@register_model_view(ObjectGroup, "bulk_delete", path="delete", detail=False)
class ObjectGroupBulkDeleteView(generic.BulkDeleteView):
    queryset = ObjectGroup.objects.all()
    table = ObjectGroupTable


class ObjectGroupAreaView(TemplateView):
    """
    Area overview view for /object/groups/<area>/.
    Shows groups filtered by area with main-tabs and area sub-tabs.
    """
    template_name = "netbox_nsm/objectgroup_area.html"

    def get(self, request, *args, **kwargs):
        if kwargs.get("area") is None:
            return redirect("/plugins/netbox-nsm/object/groups/srcdst/")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        area = kwargs.get("area", "srcdst")
        qs = ObjectGroup.objects.filter(area=area).prefetch_related(
            "members", "sub_groups", "tags"
        )
        table = ObjectGroupTable(qs)
        context.update({
            "title": _("Groups"),
            "main_tabs": _MAIN_TABS,
            "active_main_tab": "groups",
            "area_tabs": _AREA_TABS,
            "active_area": area,
            "table": table,
            "add_url": f"/plugins/netbox-nsm/object-groups/add/",
        })
        return context
