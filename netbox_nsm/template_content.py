from netbox.plugins import PluginTemplateExtension
from django.utils.translation import gettext_lazy as _


def _get_custom_refs_for(obj):
    """
    Return all ObjectCustomObjects that reference *obj* via an object_ref field,
    grouped by CustomType.

    Returns a list of dicts::

        [
            {
                "type_name": "test_nat",
                "type_url":  "/plugins/netbox-nsm/object/custom/types/3/",
                "add_url":   "/plugins/netbox-nsm/object/custom/objects/add/?custom_type=3",
                "items": [
                    {"obj": <ObjectCustomObject>, "field_label": "Source Address"},
                    ...
                ],
            },
            ...
        ]
    """
    from netbox_nsm.models import ObjectCustomType

    # Build canonical model string, e.g. "dcim.Device"
    app_label = obj._meta.app_label
    model_name = type(obj).__name__
    canonical = f"{app_label}.{model_name}"

    groups = []
    return_url = obj.get_absolute_url()

    for ct in ObjectCustomType.objects.all().order_by("name"):
        matching_fields = [
            fd for fd in (ct.field_definitions or [])
            if fd.get("type") == "object_ref"
            and fd.get("model", "").lower() == canonical.lower()
        ]

        # Collect existing custom objects that reference this object
        items = []
        for fd in matching_fields:
            fname = fd["name"]
            flabel = fd.get("label", fname)
            qs = ct.custom_objects.filter(**{f"field_data__{fname}__pk": obj.pk})
            for custom_obj in qs:
                items.append({"obj": custom_obj, "field_label": flabel})

        # Build add_url — pre-fill matching fields if any exist
        if matching_fields:
            pre_fill = "&".join(f"dyn_{fd['name']}={obj.pk}" for fd in matching_fields)
            add_url = (
                f"/plugins/netbox-nsm/object/custom/objects/add/"
                f"?custom_type={ct.pk}&{pre_fill}&return_url={return_url}"
            )
        else:
            add_url = (
                f"/plugins/netbox-nsm/object/custom/objects/add/"
                f"?custom_type={ct.pk}&return_url={return_url}"
            )

        groups.append({
            "type_name": ct.name,
            "type_icon": ct.icon,
            "type_url": ct.get_absolute_url(),
            "add_url": add_url,
            "items": items,
        })

    return groups


class SecurityZoneContextInfo(PluginTemplateExtension):
    models = ["netbox_nsm.securityzone"]

    def right_page(self):
        """ """
        if self.context["config"].get("address_ext_page") == "right":
            return self.x_page()
        return ""

    def left_page(self):
        """ """
        if self.context["config"].get("address_ext_page") == "left":
            return self.x_page()
        return ""

    def full_width_page(self):
        """ """
        if self.context["config"].get("address_ext_page") == "full_width":
            return self.x_page()
        return ""

    def x_page(self):
        return self.render(
            "netbox_nsm/securityzone/extend.html",
        )


class AddressContextInfo(PluginTemplateExtension):
    models = ["netbox_nsm.address"]

    def right_page(self):
        """ """
        if self.context["config"].get("address_ext_page") == "right":
            return self.x_page()
        return ""

    def left_page(self):
        """ """
        if self.context["config"].get("address_ext_page") == "left":
            return self.x_page()
        return ""

    def full_width_page(self):
        """ """
        if self.context["config"].get("address_ext_page") == "full_width":
            return self.x_page()
        return ""

    def x_page(self):
        return self.render(
            "netbox_nsm/address/extend.html",
        )


class AddressSetContextInfo(PluginTemplateExtension):
    models = ["netbox_nsm.addressset"]

    def right_page(self):
        """ """
        if self.context["config"].get("address_ext_page") == "right":
            return self.x_page()
        return ""

    def left_page(self):
        """ """
        if self.context["config"].get("address_ext_page") == "left":
            return self.x_page()
        return ""

    def full_width_page(self):
        """ """
        if self.context["config"].get("address_ext_page") == "full_width":
            return self.x_page()
        return ""

    def x_page(self):
        return self.render(
            "netbox_nsm/addressset/extend.html",
        )


class InterfaceInfo(PluginTemplateExtension):
    models = ["dcim.interface"]

    def right_page(self):
        """ """
        if self.context["config"].get("interface_ext_page") == "right":
            return self.x_page()
        return ""

    def left_page(self):
        """ """
        if self.context["config"].get("interface_ext_page") == "left":
            return self.x_page()
        return ""

    def full_width_page(self):
        """ """
        if self.context["config"].get("interface_ext_page") == "full_width":
            return self.x_page()
        return ""

    def x_page(self):
        """ """
        return self.render(
            "netbox_nsm/interface/interface_extend.html",
        )


class NsmSecurityLinksExtension(PluginTemplateExtension):
    """
    Renders a compact "NSM Security" panel in the right column of any object's
    detail page that has NSM assignments. Models that already have a dedicated
    Security tab are skipped to avoid duplication.
    """

    models = None  # Apply to ALL NetBox models

    # No models skipped — panel appears on all objects.
    _SECURITY_TAB_MODELS = frozenset()

    def right_page(self):
        from django.contrib.contenttypes.models import ContentType
        from django.urls import reverse

        obj = self.context.get("object")
        if not obj or not hasattr(obj, "pk"):
            return ""

        ct = ContentType.objects.get_for_model(obj)
        if f"{ct.app_label}.{ct.model}" in self._SECURITY_TAB_MODELS:
            return ""

        pk = obj.pk
        ct_filter = f"{ct.app_label}.{ct.model}"
        return_url = obj.get_absolute_url()

        assignment_types = []

        assignments = []
        for model, label, assign_label, list_url_name, add_url_name, field_name in assignment_types:
            qs = model.objects.filter(
                assigned_object_type=ct, assigned_object_id=pk
            ).select_related(field_name)[:10]
            items = []
            for a in qs:
                security_obj = getattr(a, field_name)
                items.append({
                    "name": str(security_obj),
                    "url": security_obj.get_absolute_url(),
                })
            assignments.append({
                "label": label,
                "assign_label": assign_label,
                "items": items,
                "list_url": (
                    reverse(list_url_name)
                    + f"?assigned_object_type={ct_filter}&assigned_object_id={pk}"
                ),
                "add_url": (
                    reverse(add_url_name)
                    + f"?assigned_object_type={ct.pk}&assigned_object_id={pk}&return_url={return_url}"
                ),
            })

        total_count = sum(len(a["items"]) for a in assignments)
        custom_refs = _get_custom_refs_for(obj)
        custom_count = sum(len(rg["items"]) for rg in custom_refs)

        # Custom Object Assignments (ObjectCustomObjectAssignment)
        from netbox_nsm.models import ObjectCustomObjectAssignment, ObjectCustomType
        coa_qs = (
            ObjectCustomObjectAssignment.objects
            .filter(assigned_object_type=ct, assigned_object_id=pk)
            .select_related("custom_object__custom_type")
        )
        coa_by_type = {}
        for coa in coa_qs:
            type_name = coa.custom_object.custom_type.name
            type_pk = coa.custom_object.custom_type.pk
            type_icon = coa.custom_object.custom_type.icon
            if type_name not in coa_by_type:
                coa_by_type[type_name] = {"type_pk": type_pk, "type_icon": type_icon, "items": []}
            coa_by_type[type_name]["items"].append(coa)
        custom_object_assignments = [
            {
                "type_name": type_name,
                "type_pk": v["type_pk"],
                "type_icon": v["type_icon"],
                "items": v["items"],
            }
            for type_name, v in sorted(coa_by_type.items())
        ]
        coa_count = sum(len(g["items"]) for g in custom_object_assignments)

        # All custom types for the Assign dropdown (via ObjectCustomObjectAssignment)
        all_custom_types = [
            {
                "type_name": ctype.name,
                "type_icon": ctype.icon,
                "add_url": (
                    reverse("plugins:netbox_nsm:objectcustomobjectassignment_add")
                    + f"?assigned_object_type={ct.pk}&assigned_object_id={pk}"
                    + f"&custom_type_pk={ctype.pk}&return_url={return_url}"
                ),
            }
            for ctype in ObjectCustomType.objects.all().order_by("name")
        ]

        return self.render(
            "netbox_nsm/inc/nsm_security_links.html",
            {
                "nsm_assignments": assignments,
                "nsm_total_count": total_count,
                "nsm_custom_refs": custom_refs,
                "nsm_custom_count": custom_count,
                "nsm_custom_object_assignments": custom_object_assignments,
                "nsm_coa_count": coa_count,
                "nsm_all_custom_types": all_custom_types,
            },
        )


template_extensions = [
    SecurityZoneContextInfo,
    AddressContextInfo,
    AddressSetContextInfo,
    InterfaceInfo,
    NsmSecurityLinksExtension,
]
