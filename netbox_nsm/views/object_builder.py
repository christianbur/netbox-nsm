from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django_tables2 import RequestConfig

from netbox_nsm.models import NSMTypeConfig, SecurityArea
from netbox_nsm.tables import NSMTypeConfigTable, SecurityAreaTable

__all__ = ("ObjectBuilderView",)

DEFAULT_AREA_ORDER = {
    "source": 10,
    "destination": 20,
    "services": 30,
    "action": 40,
    "info": 50,
}

_TABS = [
    {"slug": "areas", "label": "Areas"},
    {"slug": "config", "label": "Type Config"},
]


def _build_tabs(active_slug):
    tabs = []
    for t in _TABS:
        tabs.append(
            {
                **t,
                "href": reverse("plugins:netbox_nsm:object_builder", args=[t["slug"]]),
                "active": t["slug"] == active_slug,
            }
        )
    return tabs


class ObjectBuilderView(LoginRequiredMixin, View):
    """Combined Object-Builder page: Areas / Types / Built-in tabs."""

    def get(self, request, tab="config"):
        if tab == "types":
            return redirect(
                reverse("plugins:netbox_nsm:object_builder", args=["config"])
            )
        if tab not in {t["slug"] for t in _TABS}:
            return redirect(
                reverse("plugins:netbox_nsm:object_builder", args=["config"])
            )

        context = {
            "active_tab": tab,
            "tabs": _build_tabs(tab),
        }

        if tab == "areas":
            qs = SecurityArea.objects.order_by("sort_order", "slug")
            table = SecurityAreaTable(qs)
            RequestConfig(request, paginate={"per_page": 50}).configure(table)
            context["table"] = table
            context["add_url"] = reverse("plugins:netbox_nsm:securityarea_add")

        elif tab == "config":
            qs = (
                NSMTypeConfig.objects.select_related("content_type")
                .prefetch_related("areas")
                .order_by("order_id", "content_type__app_label", "content_type__model")
            )
            table = NSMTypeConfigTable(qs)
            RequestConfig(request, paginate={"per_page": 50}).configure(table)
            context["table"] = table
            context["add_url"] = reverse("plugins:netbox_nsm:typeconfig_add")

        return render(request, "netbox_nsm/object_builder.html", context)
