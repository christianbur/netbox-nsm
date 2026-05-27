from django.shortcuts import redirect
from django.views.generic import RedirectView, TemplateView

from netbox_nsm.models import (
    SecurityArea,
    SecurityObject,
    SecurityObjectType,
)


class ObjectsSrcDstTabsView(TemplateView):
    template_name = "netbox_nsm/object_tabs.html"

    MODEL_BY_TAB = {}

    TABLE_COLUMNS_BY_TAB = {}

    TABS = ()

    default_slug = None

    def _get_custom_type_by_slug(self, slug, all_custom_types=None):
        """Return SecurityObjectType for a name-based slug or legacy ct_{pk} slug."""
        if slug.startswith("ct_"):
            try:
                pk = int(slug[3:])
            except (ValueError, TypeError):
                return None
            if all_custom_types is not None:
                return next((ct for ct in all_custom_types if ct.pk == pk), None)
            return SecurityObjectType.objects.filter(pk=pk).first()
        # Name-based slug — just query DB
        if all_custom_types is not None:
            return next((ct for ct in all_custom_types if ct.name == slug), None)
        return SecurityObjectType.objects.filter(name=slug).first()

    def _get_area_by_slug(self, slug, all_areas=None):
        if all_areas is not None:
            return next((area for area in all_areas if area.slug == slug), None)
        return SecurityArea.objects.filter(slug=slug).first()

    def get(self, request, *args, **kwargs):
        if kwargs.get("tab") is None:
            ct = SecurityObjectType.objects.select_related("area").order_by(
                "area__sort_order", "area__name", "name"
            ).first()
            if ct:
                return redirect("plugins:netbox_nsm:object_tabs", tab=ct.name)
            first_area = SecurityArea.objects.order_by("sort_order", "name", "slug").first()
            if first_area:
                return redirect("plugins:netbox_nsm:object_tabs", tab=first_area.slug)
            return redirect("plugins:netbox_nsm:object_builder_root")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tab_slug = kwargs.get("tab", self.default_slug)
        # Build dynamic custom tabs from SecurityObjectType instances (slug = type name)
        all_areas = list(SecurityArea.objects.order_by("sort_order", "name", "slug"))
        all_custom_types = list(
            SecurityObjectType.objects.select_related("area").order_by(
                "area__sort_order", "area__name", "name"
            )
        )
        custom_tabs_by_area = {a.slug: [] for a in all_areas}
        for ct in all_custom_types:
            area_slug = ct.area.slug
            if area_slug not in custom_tabs_by_area:
                custom_tabs_by_area[area_slug] = []
            custom_tabs_by_area[area_slug].append({
                "slug": ct.name,
                "label": ct.name,
                "list_url_name": None,
                "add_url_name": "plugins:netbox_nsm:objectcustom_add",
                "permission": "netbox_nsm.view_securityobject",
            })

        all_dynamic_tabs = [t for slug_tabs in custom_tabs_by_area.values() for t in slug_tabs]
        all_tabs = self.TABS + tuple(all_dynamic_tabs)
        tab_map_full = {tab["slug"]: tab for tab in all_tabs}

        active_ct = self._get_custom_type_by_slug(tab_slug, all_custom_types)
        active_area = self._get_area_by_slug(tab_slug, all_areas)
        if not active_ct and not active_area and all_custom_types:
            # Unknown slug — fall back to first custom type
            active_ct = all_custom_types[0]
        if active_ct:
            active_tab = tab_map_full.get(active_ct.name)
            active_main_tab = active_ct.area.slug
            add_url = f"/plugins/netbox-nsm/object/custom/objects/add/?custom_type={active_ct.pk}"
        elif active_area:
            active_tab = None
            active_main_tab = active_area.slug
            add_url = "/plugins/netbox-nsm/object-builder/types/"
        else:
            active_tab = None
            active_main_tab = all_areas[0].slug if all_areas else "srcdst"
            add_url = "/plugins/netbox-nsm/object-builder/types/"

        # Build dynamic tab_groups from SecurityArea
        tab_groups_with_custom = [
            {
                "slug": a.slug,
                "label": a.name,
                "tabs": tuple(t["slug"] for t in custom_tabs_by_area.get(a.slug, [])),
            }
            for a in all_areas
        ]

        # Build main_tabs dynamically
        first_type_by_area = {}
        for ct in all_custom_types:
            if ct.area.slug not in first_type_by_area:
                first_type_by_area[ct.area.slug] = ct.name
        main_tabs = [
            {
                "slug": a.slug,
                "label": a.name,
                "href": (
                    f"/plugins/netbox-nsm/object/{first_type_by_area[a.slug]}/"
                    if a.slug in first_type_by_area
                    else f"/plugins/netbox-nsm/object/{a.slug}/"
                ),
            }
            for a in all_areas
        ] + [
            {"slug": "groups",   "label": "Groups",          "href": "/plugins/netbox-nsm/object/groups/"},
            {"slug": "custom",   "label": "Object-Builder",  "href": "/plugins/netbox-nsm/object/custom/"},
        ]

        context.update(
            {
                "title": "Objects",
                "active_ct": active_ct,
                "main_tabs": main_tabs,
                "active_main_tab": active_main_tab,
                "tab_groups": tab_groups_with_custom,
                "tabs": all_tabs,
                "active_tab": active_tab,
                "tab_url_name": "plugins:netbox_nsm:object_tabs",
                "active_tab_add_url": add_url,
                "active_area": active_area,
                "table_columns": self._get_table_columns_for_tab(tab_slug, ct=active_ct),
                "table_rows": self._get_table_rows_for_tab(tab_slug, ct=active_ct),
            }
        )
        return context

    def _get_table_columns_for_tab(self, tab_slug, ct=None):
        if ct is None:
            ct = self._get_custom_type_by_slug(tab_slug)
        if ct:
            cols = [{"label": "Name", "accessor": "name", "link": True}]
            for fd in (ct.field_definitions or []):
                if fd.get("__meta__"):
                    continue
                cols.append({
                    "label": fd.get("label", fd["name"]),
                    "accessor": f"field:{fd['name']}",
                })
            cols.append({"label": "Description", "accessor": "description"})
            return tuple(cols)
        return self.TABLE_COLUMNS_BY_TAB.get(tab_slug, ())

    def _get_objects_for_tab(self, tab_slug, ct=None):
        if ct is None:
            ct = self._get_custom_type_by_slug(tab_slug)
        if ct:
            objects = list(SecurityObject.objects.filter(custom_type=ct))
            objects.sort(key=lambda obj: str(obj).lower())
            return objects
        model = self.MODEL_BY_TAB.get(tab_slug)
        if model is None:
            return []
        objects = list(model.objects.all())
        objects.sort(key=lambda obj: str(obj).lower())
        return objects

    def _get_table_rows_for_tab(self, tab_slug, ct=None):
        columns = self._get_table_columns_for_tab(tab_slug, ct=ct)
        rows = []
        is_custom = ct is not None or bool(self._get_custom_type_by_slug(tab_slug))
        for obj in self._get_objects_for_tab(tab_slug, ct=ct):
            if is_custom:
                url           = f"/plugins/netbox-nsm/object/custom/objects/{obj.pk}/"
                edit_url      = f"/plugins/netbox-nsm/custom-objects/{obj.pk}/edit/"
                del_url       = f"/plugins/netbox-nsm/custom-objects/{obj.pk}/delete/"
                changelog_url = f"/plugins/netbox-nsm/custom-objects/{obj.pk}/changelog/"
            else:
                url           = f"/plugins/netbox-nsm/object/{tab_slug}/{obj.pk}/"
                edit_url      = f"/plugins/netbox-nsm/object/{tab_slug}/{obj.pk}/edit/"
                del_url       = f"/plugins/netbox-nsm/object/{tab_slug}/{obj.pk}/delete/"
                changelog_url = f"/plugins/netbox-nsm/object/{tab_slug}/{obj.pk}/changelog/"
            row = {
                "pk": obj.pk,
                "url": url,
                "edit_url": edit_url,
                "delete_url": del_url,
                "changelog_url": changelog_url,
                "cells": [],
            }
            for column in columns:
                row["cells"].append(self._resolve_cell_value(obj, column.get("accessor")))
            rows.append(row)
        return rows

    def _resolve_cell_value(self, obj, accessor):
        if accessor.startswith("field:"):
            field_name = accessor[6:]
            field_data = getattr(obj, "field_data", {}) or {}
            value = field_data.get(field_name)
            if value is None or value == "":
                return "-"
            # object_ref: {"pk": .., "url": .., "str": ..}
            if isinstance(value, dict) and "str" in value:
                return value["str"]
            return value
        if accessor == "assigned_object_type_name":
            return getattr(getattr(obj, "assigned_object_type", None), "name", "-")
        if accessor == "application_items_display":
            items = obj.application_items.values_list("name", flat=True)
            return ", ".join(items) or "-"
        if accessor == "entry_type_label":
            return obj.get_entry_type_display()
        if accessor == "members_display":
            return self._get_group_members_display(obj)
        if accessor == "enabled_display":
            return "Enabled" if getattr(obj, "enabled", False) else "Disabled"

        value = getattr(obj, accessor, "-")
        if value in (None, ""):
            return "-"
        return value

    @staticmethod
    def _get_group_members_display(group):
        member_field = group.MEMBER_FIELD_MAP.get(group.group_type)
        if not member_field:
            return "-"

        members = list(getattr(group, member_field).all())
        if group.group_type != "groups":
            members.extend(group.groups.all())
        if not members:
            return "-"

        member_names = sorted((str(member) for member in members), key=str.lower)
        return ", ".join(member_names)


class ObjectsActionTabsView(RedirectView):
    """Legacy view – redirects to the unified object tab view."""
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        tab = kwargs.get("tab", "action")
        return f"/plugins/netbox-nsm/object/{tab}/"


class ObjectsCustomAreaView(TemplateView):
    """Dedicated area view for /object/custom/ with Types and Objects sub-tabs."""

    template_name = "netbox_nsm/security_object_area.html"

    def get(self, request, *args, **kwargs):
        tab = kwargs.get("tab")
        if tab is None:
            return redirect("/plugins/netbox-nsm/object/custom/types/")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from netbox_nsm.tables import SecurityObjectTable, SecurityObjectTypeTable

        context = super().get_context_data(**kwargs)
        tab_slug = kwargs.get("tab", "types")

        sub_tabs = (
            {"slug": "types", "label": "Types", "href": "/plugins/netbox-nsm/object/custom/types/"},
            {"slug": "objects", "label": "Objects", "href": "/plugins/netbox-nsm/object/custom/objects/"},
        )

        type_pills = []
        if tab_slug == "types":
            qs = SecurityObjectType.objects.all()
            table = SecurityObjectTypeTable(qs)
            add_url = "/plugins/netbox-nsm/object/custom/types/add/"
        else:
            # Per-type filter via GET param
            request = self.request
            type_pk = request.GET.get("type_pk")
            all_types = SecurityObjectType.objects.all().order_by("name")
            type_pills = [
                {
                    "pk": ct.pk,
                    "name": ct.name,
                    "href": f"/plugins/netbox-nsm/object/custom/objects/?type_pk={ct.pk}",
                    "active": str(ct.pk) == str(type_pk),
                }
                for ct in all_types
            ]
            qs = SecurityObject.objects.select_related("custom_type").all()
            if type_pk:
                qs = qs.filter(custom_type_id=type_pk)
            table = SecurityObjectTable(qs)
            add_url = "/plugins/netbox-nsm/object/custom/objects/add/"
            if type_pk:
                add_url += f"?custom_type={type_pk}"

        # Build main_tabs dynamically from SecurityArea
        all_areas = SecurityArea.objects.order_by("slug")
        main_tabs = [
            {"slug": a.slug, "label": a.name, "href": "/plugins/netbox-nsm/object/"}
            for a in all_areas
        ] + [
            {"slug": "groups", "label": "Groups", "href": "/plugins/netbox-nsm/object/groups/"},
            {"slug": "custom", "label": "Object-Builder", "href": "/plugins/netbox-nsm/object/custom/"},
        ]

        context.update({
            "title": "Custom Objects",
            "main_tabs": main_tabs,
            "active_main_tab": "custom",
            "sub_tabs": sub_tabs,
            "active_sub_tab": tab_slug,
            "type_pills": type_pills,
            "table": table,
            "add_url": add_url,
        })
        return context