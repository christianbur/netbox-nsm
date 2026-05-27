from django.db.models import Q
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from netbox.views import generic
from utilities.views import register_model_view, ViewTab

from netbox_nsm.filtersets import SecurityObjectGroupFilterSet
from netbox_nsm.forms import SecurityObjectGroupForm, SecurityObjectGroupFilterForm, SecurityObjectGroupBulkEditForm
from netbox_nsm.models import SecurityObjectGroup, SecurityPolicyRule
from netbox_nsm.tables import SecurityObjectGroupTable

__all__ = (
    "SecurityObjectGroupView",
    "SecurityObjectGroupListView",
    "SecurityObjectGroupEditView",
    "SecurityObjectGroupDeleteView",
    "SecurityObjectGroupBulkEditView",
    "SecurityObjectGroupBulkDeleteView",
    "SecurityObjectGroupAreaView",
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
    {"slug": "info",     "label": _("Info"),               "href": "/plugins/netbox-nsm/object/groups/info/"},
)


@register_model_view(SecurityObjectGroup)
class SecurityObjectGroupView(generic.ObjectView):
    queryset = SecurityObjectGroup.objects.prefetch_related("members__custom_type", "sub_groups", "parent_groups", "tags")
    template_name = "netbox_nsm/securityobjectgroup.html"

    def get_extra_context(self, request, instance):
        return {
            "members": instance.members.select_related("custom_type").order_by(
                "custom_type__name", "name"
            ),
            "sub_groups": instance.sub_groups.order_by("name"),
            "parent_groups": instance.parent_groups.order_by("name"),
        }


@register_model_view(SecurityObjectGroup, "list", path="", detail=False)
class SecurityObjectGroupListView(generic.ObjectListView):
    queryset = SecurityObjectGroup.objects.prefetch_related("members", "sub_groups", "tags")
    filterset = SecurityObjectGroupFilterSet
    filterset_form = SecurityObjectGroupFilterForm
    table = SecurityObjectGroupTable


@register_model_view(SecurityObjectGroup, "add", detail=False)
@register_model_view(SecurityObjectGroup, "edit")
class SecurityObjectGroupEditView(generic.ObjectEditView):
    queryset = SecurityObjectGroup.objects.all()
    form = SecurityObjectGroupForm


@register_model_view(SecurityObjectGroup, "delete")
class SecurityObjectGroupDeleteView(generic.ObjectDeleteView):
    queryset = SecurityObjectGroup.objects.all()


@register_model_view(SecurityObjectGroup, "bulk_edit", path="edit", detail=False)
class SecurityObjectGroupBulkEditView(generic.BulkEditView):
    queryset = SecurityObjectGroup.objects.all()
    filterset = SecurityObjectGroupFilterSet
    table = SecurityObjectGroupTable
    form = SecurityObjectGroupBulkEditForm


@register_model_view(SecurityObjectGroup, "bulk_delete", path="delete", detail=False)
class SecurityObjectGroupBulkDeleteView(generic.BulkDeleteView):
    queryset = SecurityObjectGroup.objects.all()
    table = SecurityObjectGroupTable


def _rules_for_group(obj):
    return SecurityPolicyRule.objects.filter(
        Q(source_groups=obj)
        | Q(destination_groups=obj)
        | Q(service_groups=obj)
        | Q(action_groups=obj)
    ).distinct()


@register_model_view(SecurityObjectGroup, "assignments")
class SecurityObjectGroupAssignmentsView(generic.ObjectView):
    queryset = SecurityObjectGroup.objects.all()
    template_name = "netbox_nsm/securityobjectgroup_assignments.html"
    tab = ViewTab(
        label=_("Assignments"),
        badge=lambda obj: _rules_for_group(obj).count(),
        weight=200,
        hide_if_empty=False,
    )

    def get_extra_context(self, request, instance):
        rules = (
            _rules_for_group(instance)
            .select_related("rulebook")
            .order_by("rulebook__name", "index", "name")
        )
        return {"firewall_rules": rules}


class SecurityObjectGroupAreaView(TemplateView):
    """
    Area overview view for /object/groups/<area>/.
    Shows groups filtered by area with main-tabs and area sub-tabs.
    """
    template_name = "netbox_nsm/securityobjectgroup_area.html"

    def get(self, request, *args, **kwargs):
        if kwargs.get("area") is None:
            return redirect("/plugins/netbox-nsm/object/groups/srcdst/")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        area = kwargs.get("area", "srcdst")
        qs = SecurityObjectGroup.objects.filter(area=area).prefetch_related(
            "members", "sub_groups", "tags"
        )
        table = SecurityObjectGroupTable(qs)
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
