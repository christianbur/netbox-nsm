import json

from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse, HttpResponseBadRequest
from django.views import View

from netbox_nsm.models import RuleObjectItem
from netbox_nsm.object_rules_utils import build_rule_name_column_filter_url
from netbox_nsm.branch_urls import with_branch_query

__all__ = ("ObjectRulesApiView",)

LIMIT = 20


class ObjectRulesApiView(View):
    """
    Lightweight JSON endpoint for lazy-loading security rule references
    for a given object (identified by content-type PK + object PK).

    GET /plugins/netbox-nsm/api/object-rules/
        ?ct_id=<int>&obj_id=<int>&offset=<int>

    Response:
        {
            "results": [
                {"area": "Action", "rule_name": "allow-rule-7",
                 "rule_url": "/plugins/...", "rulebook_name": "..."}
            ],
            "total": 1336,
            "offset": 20,
            "has_more": true
        }
    """

    def get(self, request):
        try:
            ct_id = int(request.GET["ct_id"])
            obj_id = int(request.GET["obj_id"])
            offset = max(0, int(request.GET.get("offset", 0)))
        except (KeyError, ValueError):
            return HttpResponseBadRequest("ct_id and obj_id are required integers")

        try:
            ct = ContentType.objects.get(pk=ct_id)
        except ContentType.DoesNotExist:
            return HttpResponseBadRequest("Invalid ct_id")

        qs = (
            RuleObjectItem.objects.filter(content_type=ct, object_id=obj_id)
            .select_related("rule", "rule__rulebook", "field")
            .order_by("rule__rulebook__name", "field__sort_order", "rule__index")
        )

        total = qs.count()
        batch = qs[offset : offset + LIMIT]

        results = []
        seen = set()
        for item in batch:
            key = (item.field_id, item.rule_id)
            if key in seen:
                continue
            seen.add(key)
            rulebook = item.rule.rulebook
            results.append(
                {
                    "rule_id": item.rule_id,
                    "rule_name": item.rule.name,
                    "rule_url": with_branch_query(
                        build_rule_name_column_filter_url(rulebook, item.rule),
                        request,
                    ),
                    "rule_detail_url": with_branch_query(
                        item.rule.get_absolute_url(), request
                    ),
                    "rulebook_pk": rulebook.pk if rulebook else 0,
                    "rulebook_name": rulebook.name if rulebook else "",
                    "rulebook_url": with_branch_query(
                        rulebook.get_rules_tab_url() if rulebook else "",
                        request,
                    ),
                    "field_pk": item.field_id or 0,
                    "field_name": str(item.field) if item.field else "",
                }
            )

        return JsonResponse(
            {
                "results": results,
                "total": total,
                "offset": offset + len(results),
                "has_more": (offset + LIMIT) < total,
            }
        )
