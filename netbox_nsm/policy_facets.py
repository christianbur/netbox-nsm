"""Policy page facet computation (shared by view + lazy-load API)."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from django.http import HttpRequest

from netbox_nsm.models import Rule, Rulebook


def compute_policy_facets(request: HttpRequest, instance: Rulebook) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Load all rules for the rulebook, apply nsm_q filter, return facet sidebar data.

    Returns (nsm_q_raw, facets).
    """
    from netbox_nsm.query import parse, RulebookContext, filter_rules, compute_facets
    from netbox_nsm.query.engine import prepare_rules

    nsm_q_raw = request.GET.get("nsm_q", "").strip()
    query = parse(nsm_q_raw)
    context = RulebookContext(instance)

    base_rules_qs = (
        Rule.objects.filter(rulebook=instance)
        .prefetch_related(
            "source_users",
            "destination_users",
            "object_items__field",
            "object_items__content_type",
            "group_items__field",
            "group_items__security_group",
        )
        .order_by("index")
    )
    all_rules = prepare_rules(base_rules_qs)
    filtered_rules = filter_rules(all_rules, query, context)
    facets = compute_facets(
        filtered_rules, context, all_rules=all_rules, query=query
    )
    return nsm_q_raw, facets
