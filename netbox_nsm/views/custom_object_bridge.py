from django.views.generic import TemplateView
from django.urls import reverse

from netbox_nsm.models import NsmObjectType, NsmObjectTypeField


class ObjectBuilderView(TemplateView):
    template_name = "netbox_nsm/object_builder.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["builder_cards"] = (
            {
                "title": "Object Types",
                "description": "NSM-eigene dynamische Objekttypen definieren",
                "add_url": "plugins:netbox_nsm:nsmobjecttype_add",
                "list_url": "plugins:netbox_nsm:nsmobjecttype_list",
                "count": NsmObjectType.objects.count(),
            },
            {
                "title": "Object Type Fields",
                "description": "Manage fields per object type",
                "add_url": "plugins:netbox_nsm:nsmobjecttypefield_add",
                "list_url": "plugins:netbox_nsm:nsmobjecttypefield_list",
                "count": NsmObjectTypeField.objects.count(),
            },
        )
        return context


class DynamicObjectCatalogView(TemplateView):
    template_name = "netbox_nsm/dynamic_object_catalog.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = []
        for object_type in NsmObjectType.objects.prefetch_related("fields").all().order_by("group_name", "name"):
            rows.append(
                {
                    "name": object_type.display_name,
                    "group": object_type.group_name or "-",
                    "field_count": object_type.fields.count(),
                    "object_count": object_type.nsm_objects.count(),
                    "url": reverse("plugins:netbox_nsm:nsmobjecttype", args=[object_type.pk]),
                }
            )
        context["rows"] = rows
        return context
