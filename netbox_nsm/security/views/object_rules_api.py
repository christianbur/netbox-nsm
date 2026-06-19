from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse, HttpResponseBadRequest
from django.views import View

from netbox_nsm.core.branch_urls import with_branch_query
from netbox_nsm.security.object_rules import build_cot_rule_name_column_filter_url
from netbox_nsm.security.panel import (
    API_BATCH_DEFAULT,
    fetch_cot_security_field_rules,
    iter_cot_security_panel_matches,
)

__all__ = ("ObjectRulesApiView",)

LIMIT = API_BATCH_DEFAULT


def _serialize_rule_rows(rows, request):
    results = []
    for row in rows:
        rulebook = row["rulebook"]
        rule = row["rule"]
        field = row["field"]
        results.append(
            {
                "rule_id": rule.pk,
                "rule_name": rule.name,
                "rule_url": with_branch_query(
                    build_cot_rule_name_column_filter_url(
                        rulebook.slug,
                        rule.name,
                    ),
                    request,
                ),
                "rule_detail_url": with_branch_query(
                    rule.get_absolute_url(),
                    request,
                ),
                "rulebook_pk": rulebook.pk,
                "rulebook_name": rulebook.name,
                "rulebook_url": with_branch_query(
                    rulebook.get_rules_tab_url(),
                    request,
                ),
                "field_pk": field.pk,
                "field_name": str(field.name),
            }
        )
    return results


class ObjectRulesApiView(LoginRequiredMixin, View):
    """
    Lightweight JSON endpoint for lazy-loading security rule references
    for a given object (identified by content-type PK + object PK).

    GET /plugins/netbox-nsm/api/object-rules/
        ?ct_id=<int>&obj_id=<int>&offset=<int>
        [&rulebook_pk=<int>&field_pk=<int>]

    With ``rulebook_pk`` and ``field_pk``, returns rules for one field group
    (used when expanding a field in the Security Panel accordion).

    Response:
        {
            "results": [
                {"rule_name": "allow-rule-7",
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

        rulebook_pk = request.GET.get("rulebook_pk")
        field_pk = request.GET.get("field_pk")
        if rulebook_pk is not None and field_pk is not None:
            try:
                rulebook_pk = int(rulebook_pk)
                field_pk = int(field_pk)
            except ValueError:
                return HttpResponseBadRequest(
                    "rulebook_pk and field_pk must be integers"
                )
            batch, total = fetch_cot_security_field_rules(
                ct,
                obj_id,
                rulebook_pk=rulebook_pk,
                field_pk=field_pk,
                offset=offset,
                limit=LIMIT,
            )
            results = _serialize_rule_rows(batch, request)
            next_offset = offset + len(results)
            return JsonResponse(
                {
                    "results": results,
                    "total": total,
                    "offset": next_offset,
                    "has_more": next_offset < total,
                }
            )

        from netbox_nsm.security.panel import scan_cot_security_references

        all_matches = scan_cot_security_references(ct, obj_id)
        seen = set()
        deduped = []
        for row in all_matches:
            key = (row["rulebook"].pk, row["field"].pk, row["rule"].pk)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)

        total = len(deduped)
        batch = list(
            iter_cot_security_panel_matches(
                ct,
                obj_id,
                offset=offset,
                limit=LIMIT,
            )
        )
        results = _serialize_rule_rows(batch, request)

        return JsonResponse(
            {
                "results": results,
                "total": total,
                "offset": offset + len(results),
                "has_more": (offset + len(results)) < total,
            }
        )
