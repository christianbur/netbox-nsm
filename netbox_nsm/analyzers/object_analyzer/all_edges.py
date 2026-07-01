"""Compose all analyzer edges for any NetBox object."""

from __future__ import annotations

from django.apps import apps
from django.contrib.contenttypes.models import ContentType

from .registry import AnalyzerEdge, node_from_object

_SKIP_APPS = frozenset({
    "sessions",
    "contenttypes",
    "auth",
    "admin",
    "sites",
    "netbox_branching",
})

_SKIP_MODEL_NAMES = frozenset({
    "logentry",
    "objectchange",
    "journalentry",
    "event",
    "taggeditem",
})

_SKIP_FK_FIELDS = frozenset({
    "polymorphic_ctype",
    "content_type",
    "object_type",
    "assigned_object_type",
    "termination_type",
})


def _edge_label_for_field(field, *, reverse: bool = False) -> str:
    if reverse:
        return str(field.related_model._meta.verbose_name).title()
    if field.verbose_name:
        return str(field.verbose_name).title()
    return field.name.replace("_", " ").title()


def forward_relation_edges(obj) -> list[AnalyzerEdge]:
    edges: list[AnalyzerEdge] = []
    for field in obj._meta.fields:
        if field.get_internal_type() != "ForeignKey":
            continue
        if field.name in _SKIP_FK_FIELDS:
            continue
        related = getattr(obj, field.name, None)
        if related is None:
            continue
        edges.append(
            AnalyzerEdge(
                _edge_label_for_field(field),
                field.name,
                node_from_object(related),
            )
        )

    for field in obj._meta.many_to_many:
        if field.name in ("tags",):
            continue
        label = _edge_label_for_field(field)
        try:
            rel_qs = getattr(obj, field.name).all()
        except Exception:
            continue
        for related in rel_qs:
            edges.append(AnalyzerEdge(label, field.name, node_from_object(related)))

    return edges


def reverse_fk_edges(obj) -> list[AnalyzerEdge]:
    model_class = type(obj)
    edges: list[AnalyzerEdge] = []

    for model in apps.get_models():
        if model._meta.app_label in _SKIP_APPS:
            continue
        if model._meta.model_name in _SKIP_MODEL_NAMES:
            continue
        if model is model_class:
            continue

        for field in model._meta.fields:
            if field.get_internal_type() != "ForeignKey":
                continue
            if field.related_model is not model_class:
                continue
            if field.name in _SKIP_FK_FIELDS:
                continue
            label = str(model._meta.verbose_name).title()
            try:
                qs = model.objects.filter(**{field.name: obj.pk})
                if hasattr(model.objects, "select_related"):
                    qs = qs.select_related(field.name)
                for related in qs:
                    edges.append(
                        AnalyzerEdge(label, f"rev_{field.name}", node_from_object(related))
                    )
            except Exception:
                continue

    return edges


def dcim_cable_edges(obj) -> list[AnalyzerEdge]:
    edges: list[AnalyzerEdge] = []

    cable = getattr(obj, "cable", None)
    if cable is not None:
        edges.append(AnalyzerEdge("Cable", "cable", node_from_object(cable)))

    link_peers = getattr(obj, "link_peers", None)
    if link_peers is not None:
        try:
            for peer in link_peers:
                edges.append(
                    AnalyzerEdge("Connected to", "cable_peer", node_from_object(peer))
                )
        except Exception:
            pass

    connected = getattr(obj, "connected_endpoint", None)
    if connected is not None:
        edges.append(
            AnalyzerEdge("Connected to", "connected_endpoint", node_from_object(connected))
        )

    return edges


def compose_all_edges(obj, *, extras: list[AnalyzerEdge] | None = None) -> list[AnalyzerEdge]:
    """Merge forward/reverse/cable/NSM edges without duplicates."""
    from netbox_nsm.analyzers.object_analyzer.edge_sources import (
        addr_fk_edges,
        group_m2m_edges,
        inherited_nsm_link_edges,
        nsm_link_edges,
        rule_object_item_edges,
    )

    ct = ContentType.objects.get_for_model(obj)
    seen: set[tuple[str, str]] = set()
    ordered: list[AnalyzerEdge] = []

    def add(edge: AnalyzerEdge) -> None:
        key = (edge.edge_label, edge.node.id)
        if key in seen:
            return
        seen.add(key)
        ordered.append(edge)

    for edge in forward_relation_edges(obj):
        add(edge)
    for edge in reverse_fk_edges(obj):
        add(edge)
    for edge in dcim_cable_edges(obj):
        add(edge)
    for helper in (
        group_m2m_edges,
        lambda o: nsm_link_edges(o, ct),
        lambda o: rule_object_item_edges(o, ct),
        addr_fk_edges,
        inherited_nsm_link_edges,
    ):
        try:
            for edge in helper(obj):
                add(edge)
        except Exception:
            pass
    if extras:
        for edge in extras:
            add(edge)

    return ordered
