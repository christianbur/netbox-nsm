from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from netbox.views import generic
from utilities.views import register_model_view, ViewTab

from netbox_nsm.filtersets import SecurityObjectGroupFilterSet
from netbox_nsm.forms import (
    SecurityObjectGroupForm,
    SecurityObjectGroupFilterForm,
    SecurityObjectGroupBulkEditForm,
)
from netbox_nsm.models import (
    SecurityObjectGroup,
    SecurityPolicyRule,
    SecurityArea,
)
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


def _build_main_tabs():
    areas = SecurityArea.objects.order_by("slug")
    tabs = [
        {"slug": a.slug, "label": a.name, "href": "/plugins/netbox-nsm/object/"}
        for a in areas
    ]
    tabs += [
        {
            "slug": "groups",
            "label": "Groups",
            "href": "/plugins/netbox-nsm/object/groups/",
        },
        {
            "slug": "custom",
            "label": "Object-Builder",
            "href": "/plugins/netbox-nsm/object/custom/",
        },
    ]
    return tabs


def _build_area_tabs():
    return [
        {
            "slug": a.slug,
            "label": a.name,
            "href": f"/plugins/netbox-nsm/object/groups/{a.slug}/",
        }
        for a in SecurityArea.objects.order_by("slug")
    ]


@register_model_view(SecurityObjectGroup)
class SecurityObjectGroupView(generic.ObjectView):
    queryset = SecurityObjectGroup.objects.prefetch_related(
        "sub_groups", "parent_groups", "tags"
    )
    template_name = "netbox_nsm/securityobjectgroup.html"

    def get_extra_context(self, request, instance):
        return {
            "members": [],  # members M2M removed; use SecurityObjectGroupMember
            "sub_groups": instance.sub_groups.order_by("name"),
            "parent_groups": instance.parent_groups.order_by("name"),
        }


@register_model_view(SecurityObjectGroup, "list", path="", detail=False)
class SecurityObjectGroupListView(generic.ObjectListView):
    queryset = SecurityObjectGroup.objects.prefetch_related("sub_groups", "tags")
    filterset = SecurityObjectGroupFilterSet
    filterset_form = SecurityObjectGroupFilterForm
    table = SecurityObjectGroupTable


@register_model_view(SecurityObjectGroup, "add", detail=False)
@register_model_view(SecurityObjectGroup, "edit")
class SecurityObjectGroupEditView(generic.ObjectEditView):
    queryset = SecurityObjectGroup.objects.all()
    form = SecurityObjectGroupForm
    template_name = "netbox_nsm/securityobjectgroup_edit.html"

    def get_initial(self):
        initial = super().get_initial()
        area_slug = self.request.GET.get("area")
        if area_slug:
            area = SecurityArea.objects.filter(slug=area_slug).first()
            if area:
                initial["areas"] = [area.pk]
        return initial

    def _build_member_picker_data(self):
        from netbox_nsm.display_utils import (
            get_display_template_map,
            render_object_display,
        )
        from netbox_nsm.models import NSMTypeConfig

        ct_template_map = get_display_template_map()
        areas_map = {
            str(area.pk): {
                "id": str(area.pk),
                "slug": str(area.slug),
                "name": str(area.name),
                "sort_order": int(area.sort_order),
                "types": {},
            }
            for area in SecurityArea.objects.all().order_by(
                "sort_order", "name", "slug"
            )
        }

        for tc in (
            NSMTypeConfig.objects.select_related("content_type")
            .prefetch_related("areas")
            .order_by("order_id", "content_type__app_label", "content_type__model")
        ):
            model_class = tc.content_type.model_class()
            if model_class is None:
                continue
            type_name = str(tc)
            try:
                objects = list(model_class.objects.order_by("name"))
            except Exception:
                continue
            for area in tc.areas.all():
                area_id = str(area.pk)
                area_data = areas_map.get(area_id)
                if not area_data:
                    continue
                if type_name not in area_data["types"]:
                    area_data["types"][type_name] = []
                for obj in objects:
                    area_data["types"][type_name].append(
                        {
                            "id": str(obj.pk),
                            "name": render_object_display(
                                obj, tc.content_type_id, ct_template_map
                            ),
                            "typeName": type_name,
                            "contentTypeId": tc.content_type_id,
                        }
                    )

        ordered_areas = []
        for area in sorted(
            areas_map.values(),
            key=lambda a: (a["sort_order"], a["name"].lower(), a["slug"]),
        ):
            types = []
            for type_name, entries in sorted(
                area["types"].items(), key=lambda pair: pair[0].lower()
            ):
                types.append({"name": type_name, "entries": entries})
            ordered_areas.append(
                {
                    "id": area["id"],
                    "slug": area["slug"],
                    "name": area["name"],
                    "types": types,
                }
            )

        return {"areas": ordered_areas}

    def get_extra_context(self, request, instance):
        from netbox_nsm.display_utils import (
            get_display_template_map,
            render_object_display,
        )
        from netbox_nsm.models import NSMTypeConfig

        initial_members = []
        if instance.pk:
            ct_template_map = get_display_template_map()
            tc_label_cache = {}
            for member in instance.member_items.select_related("content_type").order_by(
                "content_type__app_label", "content_type__model", "object_id"
            ):
                obj = member.assigned_object
                if obj is None:
                    continue
                ct_id = member.content_type_id
                if ct_id not in tc_label_cache:
                    tc = NSMTypeConfig.objects.filter(content_type_id=ct_id).first()
                    tc_label_cache[ct_id] = str(tc) if tc else str(member.content_type)
                initial_members.append(
                    {
                        "id": str(obj.pk),
                        "name": render_object_display(obj, ct_id, ct_template_map),
                        "typeName": tc_label_cache[ct_id],
                        "contentTypeId": ct_id,
                    }
                )
        return {
            "nsm_group_member_picker_data": self._build_member_picker_data(),
            "nsm_group_member_initial": initial_members,
        }


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
    return SecurityPolicyRule.objects.filter(group_items__security_group=obj).distinct()


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
            first = SecurityArea.objects.order_by("slug").first()
            slug = first.slug if first else "source"
            return redirect(f"/plugins/netbox-nsm/object/groups/{slug}/")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        area_slug = kwargs.get("area", "source")
        qs = (
            SecurityObjectGroup.objects.filter(areas__slug=area_slug)
            .prefetch_related("areas", "members", "sub_groups", "tags")
            .distinct()
        )
        table = SecurityObjectGroupTable(qs)
        context.update(
            {
                "title": _("Groups"),
                "main_tabs": _build_main_tabs(),
                "active_main_tab": "groups",
                "area_tabs": _build_area_tabs(),
                "active_area": area_slug,
                "table": table,
                "add_url": f"/plugins/netbox-nsm/object-groups/add/?area={area_slug}",
            }
        )
        return context
