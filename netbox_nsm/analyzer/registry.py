from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

__all__ = ["AnalyzerNode", "AnalyzerEdge", "AnalyzerRegistry", "node_from_object", "registry"]

# ── Node-type → (icon_emoji, hex_color, bg_color) ──────────────────────────
_NODE_STYLES: dict[str, tuple[str, str, str]] = {
    "device":    ("🖥",  "#0d6efd", "#dbeafe"),
    "vm":        ("☁",  "#0891b2", "#cffafe"),
    "interface": ("🔌", "#6c757d", "#e9ecef"),
    "ip":        ("●",  "#16a34a", "#dcfce7"),
    "prefix":    ("⊞",  "#0d9488", "#ccfbf1"),
    "iprange":   ("↔",  "#d97706", "#fef3c7"),
    "vlan":      ("📡", "#ea580c", "#ffedd5"),
    "vrf":       ("⇄",  "#7c3aed", "#ede9fe"),
    "label":     ("🏷", "#c026d3", "#fae8ff"),
    "zone":      ("🛡", "#dc3545", "#ffe4e6"),
    "group":     ("⬡",  "#78716c", "#f5f5f4"),
    "rule":      ("⚡", "#e85f00", "#fff7ed"),
    "rulebook":  ("📘", "#374151", "#f3f4f6"),
    "site":      ("📍", "#0369a1", "#eff6ff"),
    "tenant":    ("🏢", "#15803d", "#f0fdf4"),
    "object":    ("◆",  "#64748b", "#f8fafc"),
}

# ── Model → node_type string ────────────────────────────────────────────────
_MODEL_TYPE_MAP: dict[tuple[str, str], str] = {
    ("dcim", "device"):                        "device",
    ("virtualization", "virtualmachine"):       "vm",
    ("dcim", "interface"):                     "interface",
    ("virtualization", "vminterface"):          "interface",
    ("ipam", "ipaddress"):                     "ip",
    ("ipam", "prefix"):                        "prefix",
    ("ipam", "iprange"):                       "iprange",
    ("ipam", "vlan"):                          "vlan",
    ("ipam", "vrf"):                           "vrf",
    ("dcim", "site"):                          "site",
    ("dcim", "location"):                      "site",
    ("tenancy", "tenant"):                     "tenant",
    ("netbox_nsm", "securitypolicyrule"):      "rule",
    ("netbox_nsm", "securitypolicyrulebook"):  "rulebook",
    ("netbox_nsm", "securityarea"):            "zone",
}


def _get_node_type(obj: Any) -> str:
    key = (obj._meta.app_label, obj._meta.model_name)
    if key in _MODEL_TYPE_MAP:
        return _MODEL_TYPE_MAP[key]
    # netbox_custom_objects: infer type from verbose_name / name prefix
    vn = obj._meta.verbose_name.lower()
    name = getattr(obj, "name", "") or ""
    if "address" in vn and name.lower().startswith("ag-"):
        return "group"
    if "label" in vn:
        return "label"
    if "zone" in vn:
        return "zone"
    if "group" in vn:
        return "group"
    return "object"


@dataclass
class AnalyzerNode:
    id: str          # "{ct_id}:{object_id}"
    ct_id: int
    object_id: int
    node_type: str
    type_label: str  # human-readable "App › Type" e.g. "IPAM › Prefix"
    label: str
    url: str
    icon: str = "◆"
    color: str = "#64748b"
    bg_color: str = "#f8fafc"


@dataclass
class AnalyzerEdge:
    edge_label: str
    edge_type: str
    node: AnalyzerNode


def node_from_object(obj: Any) -> AnalyzerNode:
    """Build an AnalyzerNode from any NetBox model instance."""
    from django.contrib.contenttypes.models import ContentType
    from netbox_nsm.display_utils import get_display_template_map, render_object_display, ct_display_label

    ct = ContentType.objects.get_for_model(obj)
    node_type = _get_node_type(obj)
    icon, color, bg = _NODE_STYLES.get(node_type, _NODE_STYLES["object"])
    label = render_object_display(obj, ct.pk, get_display_template_map())
    url = obj.get_absolute_url() if hasattr(obj, "get_absolute_url") else "#"

    return AnalyzerNode(
        id=f"{ct.pk}:{obj.pk}",
        ct_id=ct.pk,
        object_id=obj.pk,
        node_type=node_type,
        type_label=ct_display_label(ct),
        label=str(label),
        url=url,
        icon=icon,
        color=color,
        bg_color=bg,
    )


class AnalyzerRegistry:
    """Maps model classes to edge-resolver functions.

    Usage::

        @registry.register(MyModel)
        def _my_model(obj):
            return [AnalyzerEdge(...), ...]

        # Optional catch-all for unregistered models:
        registry.set_fallback(my_fallback_fn)
    """

    def __init__(self) -> None:
        self._resolvers: list[tuple[type, Callable]] = []
        self._fallback: Callable | None = None

    def register(self, model_class: type) -> Callable:
        """Decorator: ``@registry.register(MyModel)``."""
        def decorator(fn: Callable) -> Callable:
            self._resolvers.append((model_class, fn))
            return fn
        return decorator

    def set_fallback(self, fn: Callable) -> None:
        """Register a catch-all resolver for unregistered model types."""
        self._fallback = fn

    def get_edges(self, obj: Any) -> list[AnalyzerEdge]:
        model_class = type(obj)
        for mc, fn in self._resolvers:
            if mc is model_class:
                try:
                    return list(fn(obj))
                except Exception:
                    return []
        if self._fallback is not None:
            try:
                return list(self._fallback(obj))
            except Exception:
                return []
        return []


# Singleton – import and use everywhere
registry = AnalyzerRegistry()
