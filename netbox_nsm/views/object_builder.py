import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django_tables2 import RequestConfig

from netbox_nsm.builtin_types import BUILTIN_CUSTOM_TYPES
from netbox_nsm.models import SecurityArea, SecurityObject, SecurityObjectType
from netbox_nsm.tables import SecurityAreaTable, SecurityObjectTypeTable

__all__ = ("ObjectBuilderView",)

_TABS = [
    {"slug": "types",   "label": "Types"},
    {"slug": "areas",   "label": "Areas"},
    {"slug": "builtin", "label": "Built-in"},
]


def _build_tabs(active_slug):
    tabs = []
    for t in _TABS:
        tabs.append({
            **t,
            "href": reverse("plugins:netbox_nsm:object_builder", args=[t["slug"]]),
            "active": t["slug"] == active_slug,
        })
    return tabs


class ObjectBuilderView(LoginRequiredMixin, View):
    """Combined Object-Builder page: Areas / Types / Built-in tabs."""

    def get(self, request, tab="types"):
        if tab not in {t["slug"] for t in _TABS}:
            return redirect(reverse("plugins:netbox_nsm:object_builder", args=["types"]))

        context = {
            "active_tab": tab,
            "tabs": _build_tabs(tab),
        }

        if tab == "types":
            qs = SecurityObjectType.objects.select_related("area").order_by("area__slug", "name")
            table = SecurityObjectTypeTable(qs)
            RequestConfig(request, paginate={"per_page": 50}).configure(table)
            context["table"] = table
            context["add_url"] = reverse("plugins:netbox_nsm:securityobjecttype_add")

        elif tab == "areas":
            qs = SecurityArea.objects.order_by("slug")
            table = SecurityAreaTable(qs)
            RequestConfig(request, paginate={"per_page": 50}).configure(table)
            context["table"] = table
            context["add_url"] = reverse("plugins:netbox_nsm:securityarea_add")

        elif tab == "builtin":
            installed_names = set(SecurityObjectType.objects.values_list("name", flat=True))
            enriched = []
            for t in BUILTIN_CUSTOM_TYPES:
                fds_display = [fd for fd in t.get("field_definitions", []) if not fd.get("__meta__")]
                enriched.append({
                    **t,
                    "already_installed": t["name"] in installed_names,
                    "field_definitions_json": json.dumps(fds_display, ensure_ascii=False, indent=2),
                })
            context["builtin_types"] = enriched

        return render(request, "netbox_nsm/object_builder.html", context)

    def post(self, request, tab="builtin"):
        if not request.user.has_perm("netbox_nsm.add_securityobjecttype"):
            messages.error(request, "Permission denied.")
            return redirect(reverse("plugins:netbox_nsm:object_builder", args=["builtin"]))

        install_one = request.POST.get("install_one")
        if install_one is not None:
            selected_indices = [install_one]
        else:
            selected_indices = request.POST.getlist("selected")
        created = 0
        for idx_str in selected_indices:
            try:
                t = BUILTIN_CUSTOM_TYPES[int(idx_str)]
            except (ValueError, IndexError):
                continue
            custom_name = request.POST.get(f"name_{idx_str}", t["name"]).strip()
            custom_template = request.POST.get(
                f"display_template_{idx_str}",
                t.get("display_template", ""),
            ).strip()
            if not custom_name:
                continue
            if SecurityObjectType.objects.filter(name=custom_name).exists():
                messages.warning(request, f"'{custom_name}' existiert bereits — übersprungen.")
                continue
            area_obj = SecurityArea.objects.filter(slug=t["area"]).first()
            if not area_obj:
                messages.warning(request, f"Area '{t['area']}' nicht gefunden — '{custom_name}' übersprungen.")
                continue
            obj_type = SecurityObjectType.objects.create(
                name=custom_name,
                area=area_obj,
                description=t.get("description", ""),
                field_definitions=t.get("field_definitions", []),
                display_template=custom_template,
            )
            for default_obj in t.get("default_objects", []):
                SecurityObject.objects.get_or_create(
                    name=default_obj["name"],
                    custom_type=obj_type,
                    defaults={"field_data": default_obj.get("field_data", {})},
                )
            created += 1

        if created:
            messages.success(request, f"{created} Typ(en) installiert.")
        return redirect(reverse("plugins:netbox_nsm:object_builder", args=["builtin"]))
