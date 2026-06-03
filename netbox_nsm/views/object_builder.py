from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django_tables2 import RequestConfig

from netbox_nsm.models import SecurityArea
from netbox_nsm.tables import SecurityAreaTable

__all__ = ("ObjectBuilderView",)


class ObjectBuilderView(LoginRequiredMixin, View):
    """Object-Builder page: Areas tab."""

    def get(self, request, tab="areas"):
        if tab not in {"areas"}:
            return redirect(reverse("plugins:netbox_nsm:object_builder", args=["areas"]))

        qs = SecurityArea.objects.order_by("sort_order", "slug")
        table = SecurityAreaTable(qs)
        RequestConfig(request, paginate={"per_page": 50}).configure(table)

        context = {
            "active_tab": "areas",
            "table": table,
            "add_url": reverse("plugins:netbox_nsm:securityarea_add"),
        }
        return render(request, "netbox_nsm/object_builder.html", context)
