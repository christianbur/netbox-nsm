"""Object Analyzer view modes and server-side edge filtering.

Modes control which relation targets appear in the graph and link picker.
Filtering is applied in Python (``filter_edges_for_mode``); the frontend only
passes ``mode=all|security`` on page load and API calls.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from netbox_nsm.analysis.analyzer.registry import AnalyzerEdge

__all__ = (
    "AnalyzerMode",
    "SECURITY_ALLOWED_MODELS",
    "SECURITY_DENIED_EDGE_TYPES",
    "SECURITY_DENIED_NODE_TYPES",
    "SECURITY_NSM_COT_SLUGS",
    "clear_security_mode_cache",
    "edge_allowed_in_security",
    "filter_edges_for_mode",
    "get_filtered_edges",
    "get_security_allowed_ct_ids",
    "parse_analyzer_mode",
)


class AnalyzerMode(str, Enum):
    ALL = "all"
    SECURITY = "security"


# ── Static allowlist: NetBox core models (app_label, model_name) ─────────────
SECURITY_ALLOWED_MODELS = frozenset({
    # Hosts
    ("dcim", "device"),
    ("virtualization", "virtualmachine"),
    # Interfaces
    ("dcim", "interface"),
    ("virtualization", "vminterface"),
    # IPAM
    ("ipam", "ipaddress"),
    ("ipam", "prefix"),
    ("ipam", "iprange"),
})

# NSM Custom Object Type slugs allowed in Security mode
SECURITY_NSM_COT_SLUGS = frozenset({
    "nsm_address",
    "nsm_address_custom",
    "nsm_address_group",
    "nsm_object_link",
    "nsm_service",
    "nsm_service_group",
    "nsm_action",
    "nsm_app_business",
    "nsm_app_network",
})

# Edge resolver keys excluded in Security mode (cable / rule plumbing)
SECURITY_DENIED_EDGE_TYPES = frozenset({
    "in_rule",
    "in_rulebook",
    "cable",
    "cable_peer",
    "connected_endpoint",
})

# Node-type hints excluded even when the backing model is generic ``object``
SECURITY_DENIED_NODE_TYPES = frozenset({
    "label",
    "zone",
    "rule",
    "rulebook",
    "vlan",
    "vrf",
    "site",
    "tenant",
})

# Reverse-FK / relation category labels hidden in Security mode
_SECURITY_DENIED_EDGE_LABELS_NORM = frozenset({
    "label",
    "labels",
    "zone",
    "zones",
    "rule",
    "rules",
    "rulebook",
    "rulebooks",
    "regel",
    "cable",
    "cable termination",
    "cable terminations",
    "console port",
    "console ports",
    "console server port",
    "console server ports",
    "connected to",
    "power port",
    "power outlet",
    "front port",
    "rear port",
    "vlan",
    "vlans",
    "vrf",
    "vrfs",
    "site",
    "sites",
    "tenant",
    "tenants",
    "location",
    "locations",
    "rack",
    "racks",
    "circuit",
    "circuits",
})


def parse_analyzer_mode(value: str | None) -> AnalyzerMode:
    if value == AnalyzerMode.SECURITY.value:
        return AnalyzerMode.SECURITY
    return AnalyzerMode.ALL


def clear_security_mode_cache() -> None:
    _security_allowed_ct_ids_tuple.cache_clear()


@lru_cache(maxsize=1)
def _security_allowed_ct_ids_tuple() -> tuple[int, ...]:
    from django.contrib.contenttypes.models import ContentType

    from netbox_nsm.objects.type_config_specs import content_type_ids_for_cot_slugs

    ids: set[int] = set()
    for app_label, model_name in SECURITY_ALLOWED_MODELS:
        try:
            ct = ContentType.objects.get(app_label=app_label, model=model_name)
        except ContentType.DoesNotExist:
            continue
        ids.add(ct.pk)

    ids.update(content_type_ids_for_cot_slugs(sorted(SECURITY_NSM_COT_SLUGS)))
    return tuple(sorted(ids))


def get_security_allowed_ct_ids() -> frozenset[int]:
    return frozenset(_security_allowed_ct_ids_tuple())


def _normalize_edge_label(label: str) -> str:
    text = (label or "").strip().lower()
    if text.startswith("regel"):
        return "regel"
    return text


def edge_allowed_in_security(edge: AnalyzerEdge, allowed_ct_ids: frozenset[int]) -> bool:
    if edge.edge_type in SECURITY_DENIED_EDGE_TYPES:
        return False
    if edge.node.node_type in SECURITY_DENIED_NODE_TYPES:
        return False
    norm_label = _normalize_edge_label(edge.edge_label)
    if norm_label in _SECURITY_DENIED_EDGE_LABELS_NORM:
        return False
    if norm_label.startswith("regel"):
        return False
    return edge.node.ct_id in allowed_ct_ids


def filter_edges_for_mode(
    edges: list[AnalyzerEdge],
    mode: AnalyzerMode,
) -> list[AnalyzerEdge]:
    if mode is AnalyzerMode.ALL:
        return edges
    allowed = get_security_allowed_ct_ids()
    return [edge for edge in edges if edge_allowed_in_security(edge, allowed)]


def get_filtered_edges(obj, mode: AnalyzerMode) -> list[AnalyzerEdge]:
    from netbox_nsm.analysis.analyzer.registry import registry

    return filter_edges_for_mode(registry.get_edges(obj), mode)
