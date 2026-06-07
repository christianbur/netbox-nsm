from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from netbox.views import generic
from utilities.views import register_model_view, ViewTab

from netbox_nsm.filtersets import ObjectGroupFilterSet
from netbox_nsm.forms import (
    ObjectGroupForm,
    ObjectGroupFilterForm,
    ObjectGroupBulkEditForm,
)
from netbox_nsm.models import (
    ObjectGroup,
    Rule,
)
from netbox_nsm.panel_sections import get_default_panel_slug, get_panel_sections
from netbox_nsm.setup_flags import setup_menu_enabled
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


def _build_main_tabs():
    tabs = [
        {
            "slug": section["slug"],
            "label": section["name"],
            "href": "/plugins/netbox-nsm/object/",
        }
        for section in get_panel_sections()
    ]
    tabs += [
        {
            "slug": "groups",
            "label": str(_("Groups")),
            "href": "/plugins/netbox-nsm/object/groups/",
        },
    ]
    if setup_menu_enabled():
        tabs.append(
            {
                "slug": "setup",
                "label": str(_("Setup")),
                "href": "/plugins/netbox-nsm/setup/",
            }
        )
    return tabs


def _build_area_tabs():
    return [
        {
            "slug": section["slug"],
            "label": section["name"],
            "href": f"/plugins/netbox-nsm/object/groups/{section['slug']}/",
        }
        for section in get_panel_sections()
    ]


@register_model_view(ObjectGroup)
class ObjectGroupView(generic.ObjectView):
    queryset = ObjectGroup.objects.prefetch_related(
        "sub_groups", "parent_groups", "tags"
    )
    template_name = "netbox_nsm/objectgroup.html"

    def get_extra_context(self, request, instance):
        return {
            "members": [],
            "sub_groups": instance.sub_groups.order_by("name"),
            "parent_groups": instance.parent_groups.order_by("name"),
        }


@register_model_view(ObjectGroup, "list", path="", detail=False)
class ObjectGroupListView(generic.ObjectListView):
    queryset = ObjectGroup.objects.prefetch_related("sub_groups", "tags")
    filterset = ObjectGroupFilterSet
    filterset_form = ObjectGroupFilterForm
    table = ObjectGroupTable


@register_model_view(ObjectGroup, "add", detail=False)
@register_model_view(ObjectGroup, "edit")
class ObjectGroupEditView(generic.ObjectEditView):
    queryset = ObjectGroup.objects.all()
    form = ObjectGroupForm
    template_name = "netbox_nsm/objectgroup_edit.html"

    def get_initial(self):
        initial = super().get_initial()
        area_slug = self.request.GET.get("area")
        if area_slug:
            initial["field_slugs"] = [area_slug]
        return initial

    def _build_member_picker_data(self):
        from netbox_nsm.display_utils import (
            get_display_template_map,
            render_object_display,
        )
        from netbox_nsm.models import TypeConfig

        ct_template_map = get_display_template_map()
        areas_map = {
            section["slug"]: {
                "id": section["slug"],
                "slug": section["slug"],
                "name": str(section["name"]),
                "sort_order": int(section["sort_order"]),
                "types": {},
            }
            for section in get_panel_sections()
        }

        for tc in TypeConfig.objects.select_related("content_type").order_by(
            "order_id", "content_type__app_label", "content_type__model"
        ):
            model_class = tc.content_type.model_class()
            if model_class is None:
                continue
            type_name = str(tc)
            try:
                objects = list(model_class.objects.order_by("name"))
            except Exception:
                continue
            for slug in tc.panel_slugs or []:
                area_data = areas_map.get(slug)
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
        from netbox_nsm.models import TypeConfig

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
                    tc = TypeConfig.objects.filter(content_type_id=ct_id).first()
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


def _rules_for_group(obj):
    return Rule.objects.filter(group_items__security_group=obj).distinct()


@register_model_view(ObjectGroup, "assignments")
class ObjectGroupAssignmentsView(generic.ObjectView):
    queryset = ObjectGroup.objects.all()
    template_name = "netbox_nsm/objectgroup_assignments.html"
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
            .prefetch_related(
                "object_items__field",
                "group_items__field",
                "group_items__security_group",
            )
            .order_by("rulebook__name", "index", "name")
        )
        return {"firewall_rules": rules}


class ObjectGroupAreaView(TemplateView):
    """Area overview view for /object/groups/<area>/."""

    template_name = "netbox_nsm/objectgroup_area.html"

    def get(self, request, *args, **kwargs):
        if kwargs.get("area") is None:
            return redirect(
                f"/plugins/netbox-nsm/object/groups/{get_default_panel_slug()}/"
            )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        area_slug = kwargs.get("area", get_default_panel_slug())
        qs = (
            ObjectGroup.objects.filter(field_slugs__contains=[area_slug])
            .prefetch_related("sub_groups", "tags")
            .distinct()
        )
        table = ObjectGroupTable(qs)
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
