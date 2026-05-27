from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.views import View
from django.shortcuts import render

from netbox_nsm.models import SecurityObjectAssignment, SecurityPolicyRule, SecurityObject

__all__ = ("DeviceMatchingRulesView", "GlobalRulesSearchView")


def _get_label_pks(obj):
    """Return sorted list of SecurityObject PKs assigned to obj."""
    ct = ContentType.objects.get_for_model(obj)
    return list(
        SecurityObjectAssignment.objects
        .filter(assigned_object_type=ct, assigned_object_id=obj.pk)
        .select_related("custom_object")
        .order_by("custom_object__name")
        .values_list("custom_object_id", flat=True)
    )


def _get_label_objects(obj):
    """Return sorted list of SecurityObject instances assigned to obj."""
    ct = ContentType.objects.get_for_model(obj)
    return list(
        SecurityObjectAssignment.objects
        .filter(assigned_object_type=ct, assigned_object_id=obj.pk)
        .select_related("custom_object__custom_type")
        .order_by("custom_object__name")
        .values_list("custom_object", flat=False)
    )


def get_matching_rules(label_pks):
    """
    Return (src_rules, dst_rules) QuerySets where all label_pks are
    a subset of the rule's source or destination custom objects.
    """
    n = len(label_pks)
    if n == 0:
        empty = SecurityPolicyRule.objects.none()
        return empty, empty

    src_rules = (
        SecurityPolicyRule.objects
        .annotate(
            src_matched=Count(
                "custom_srcdst_objects",
                filter=Q(custom_srcdst_objects__in=label_pks),
                distinct=True,
            )
        )
        .filter(src_matched=n)
        .select_related("rulebook")
        .prefetch_related("custom_srcdst_objects", "destination_custom_objects",
                          "custom_action_objects", "source_zones", "destination_zones")
    )

    dst_rules = (
        SecurityPolicyRule.objects
        .annotate(
            dst_matched=Count(
                "destination_custom_objects",
                filter=Q(destination_custom_objects__in=label_pks),
                distinct=True,
            )
        )
        .filter(dst_matched=n)
        .select_related("rulebook")
        .prefetch_related("custom_srcdst_objects", "destination_custom_objects",
                          "custom_action_objects", "source_zones", "destination_zones")
    )

    return src_rules, dst_rules


class DeviceMatchingRulesView(View):
    template_name = "netbox_nsm/device_matching_rules.html"

    def get(self, request, pk):
        obj_type = request.GET.get("type", "device")

        if obj_type == "vm":
            from virtualization.models import VirtualMachine
            obj = get_object_or_404(VirtualMachine, pk=pk)
            obj_kind = "Virtual Machine"
        else:
            from dcim.models import Device
            obj = get_object_or_404(Device, pk=pk)
            obj_kind = "Device"

        # Sorted labels assigned to this object
        ct = ContentType.objects.get_for_model(obj)
        assignments = (
            SecurityObjectAssignment.objects
            .filter(assigned_object_type=ct, assigned_object_id=obj.pk)
            .select_related("custom_object__custom_type")
            .order_by("custom_object__name")
        )
        labels = [a.custom_object for a in assignments]
        label_pks = [lbl.pk for lbl in labels]

        src_rules, dst_rules = get_matching_rules(label_pks)

        return render(request, self.template_name, {
            "object": obj,
            "obj_kind": obj_kind,
            "labels": labels,
            "src_rules": list(src_rules),
            "dst_rules": list(dst_rules),
        })


class GlobalRulesSearchView(View):
    """
    Global rule search across ALL rulebooks, grouped by rulebook.
    Accepts src_obj_id / dst_obj_id GET params (subset matching).
    add_q GET param: search SecurityObject by name to add to filter.
    URL: /plugins/netbox-nsm/rules/search/?src_obj_id=3&src_obj_id=7
    """
    template_name = "netbox_nsm/global_rules_search.html"

    def get(self, request):
        src_obj_ids = [v for v in request.GET.getlist("src_obj_id") if v.isdigit()]
        dst_obj_ids = [v for v in request.GET.getlist("dst_obj_id") if v.isdigit()]
        add_q = request.GET.get("add_q", "").strip()

        src_obj_ids_int = [int(v) for v in src_obj_ids]
        dst_obj_ids_int = [int(v) for v in dst_obj_ids]

        src_objects = (
            list(SecurityObject.objects.filter(pk__in=src_obj_ids_int)
                 .select_related("custom_type").order_by("name"))
            if src_obj_ids_int else []
        )
        dst_objects = (
            list(SecurityObject.objects.filter(pk__in=dst_obj_ids_int)
                 .select_related("custom_type").order_by("name"))
            if dst_obj_ids_int else []
        )

        # Object search suggestions to add to filter
        add_suggestions = []
        if add_q:
            add_suggestions = list(
                SecurityObject.objects.filter(name__icontains=add_q)
                .select_related("custom_type")
                .exclude(pk__in=src_obj_ids_int + dst_obj_ids_int)
                .order_by("custom_type__name", "name")[:20]
            )

        # Build remove-URLs for each active filter object
        def _remove_url(remove_pk, id_list, param):
            from urllib.parse import urlencode
            remaining = [v for v in id_list if v != str(remove_pk)]
            params = [(param, v) for v in remaining]
            other_param = "dst_obj_id" if param == "src_obj_id" else "src_obj_id"
            other_list = dst_obj_ids if param == "src_obj_id" else src_obj_ids
            params += [(other_param, v) for v in other_list]
            qs = urlencode(params)
            return request.path + ("?" + qs if qs else "")

        src_objects_with_remove = [
            {"obj": o, "remove_url": _remove_url(o.pk, src_obj_ids, "src_obj_id")}
            for o in src_objects
        ]
        dst_objects_with_remove = [
            {"obj": o, "remove_url": _remove_url(o.pk, dst_obj_ids, "dst_obj_id")}
            for o in dst_objects
        ]

        # Build add-URLs for suggestions
        def _add_url(new_pk, param):
            from urllib.parse import urlencode
            params = [(param, v) for v in (src_obj_ids if param == "src_obj_id" else dst_obj_ids)]
            params.append((param, str(new_pk)))
            other_param = "dst_obj_id" if param == "src_obj_id" else "src_obj_id"
            other_list = dst_obj_ids if param == "src_obj_id" else src_obj_ids
            params += [(other_param, v) for v in other_list]
            return request.path + "?" + urlencode(params)

        add_suggestions_with_url = [
            {"obj": s, "add_src_url": _add_url(s.pk, "src_obj_id"),
             "add_dst_url": _add_url(s.pk, "dst_obj_id")}
            for s in add_suggestions
        ]

        # Query and group by rulebook
        rulebook_groups = []
        if src_obj_ids_int or dst_obj_ids_int:
            rules_qs = SecurityPolicyRule.objects.select_related("rulebook").prefetch_related(
                "custom_srcdst_objects__custom_type",
                "destination_custom_objects__custom_type",
                "custom_action_objects__custom_type",
                "source_zones",
                "destination_zones",
            )
            if src_obj_ids_int:
                n = len(src_obj_ids_int)
                rules_qs = rules_qs.annotate(
                    _src_matched=Count(
                        "custom_srcdst_objects",
                        filter=Q(custom_srcdst_objects__id__in=src_obj_ids_int),
                        distinct=True,
                    )
                ).filter(_src_matched=n)
            elif dst_obj_ids_int:
                n = len(dst_obj_ids_int)
                rules_qs = rules_qs.annotate(
                    _dst_matched=Count(
                        "destination_custom_objects",
                        filter=Q(destination_custom_objects__id__in=dst_obj_ids_int),
                        distinct=True,
                    )
                ).filter(_dst_matched=n)

            from collections import defaultdict
            from urllib.parse import urlencode
            groups = defaultdict(list)
            for rule in rules_qs:
                groups[rule.rulebook].append(rule)

            params = urlencode(
                [("src_obj_id", v) for v in src_obj_ids]
                + [("dst_obj_id", v) for v in dst_obj_ids]
            )
            from django.urls import reverse as _reverse
            for rulebook, rules in sorted(groups.items(), key=lambda x: x[0].name if x[0] else ""):
                policy_url = (
                    _reverse("plugins:netbox_nsm:securitypolicyrulebook_policy",
                              args=[rulebook.pk]) + "?" + params
                ) if rulebook else ""
                rulebook_groups.append({
                    "rulebook": rulebook,
                    "rules": rules,
                    "policy_url": policy_url,
                })

        return render(request, self.template_name, {
            "src_objects": src_objects_with_remove,
            "dst_objects": dst_objects_with_remove,
            "add_suggestions": add_suggestions_with_url,
            "add_q": add_q,
            "rulebook_groups": rulebook_groups,
            "src_obj_ids": src_obj_ids,
            "dst_obj_ids": dst_obj_ids,
            "total_count": sum(len(g["rules"]) for g in rulebook_groups),
        })
