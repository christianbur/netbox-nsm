"""Parent host (device / VM) links for DCIM and virtualization interfaces."""

from __future__ import annotations

from django.db.models import prefetch_related_objects

__all__ = (
    "get_interface_parent_host",
    "interface_parent_host_payload",
    "prefetch_interface_parents",
)

_INTERFACE_MODEL_LABELS = frozenset(
    {"dcim.interface", "virtualization.vminterface"},
)


def _is_interface_model(obj) -> bool:
    meta = getattr(obj, "_meta", None)
    if meta is None:
        return False
    return getattr(meta, "label_lower", "") in _INTERFACE_MODEL_LABELS


def prefetch_interface_parents(objects) -> None:
    """Avoid N+1 when resolving interface → device/VM parents."""
    try:
        from dcim.models import Interface
        from virtualization.models import VMInterface
    except ImportError:
        return

    device_ifaces = [obj for obj in objects or [] if isinstance(obj, Interface)]
    vm_ifaces = [obj for obj in objects or [] if isinstance(obj, VMInterface)]
    if device_ifaces:
        prefetch_related_objects(device_ifaces, "device")
    if vm_ifaces:
        prefetch_related_objects(vm_ifaces, "virtual_machine")


def get_interface_parent_host(obj):
    """Return parent host instance (Device or VirtualMachine) for an interface."""
    if obj is None or not _is_interface_model(obj):
        return None
    label = obj._meta.label_lower
    if label == "dcim.interface":
        return getattr(obj, "device", None)
    if label == "virtualization.vminterface":
        return getattr(obj, "virtual_machine", None)
    return None


def interface_parent_host_payload(obj) -> dict:
    """URL + display name for Security Panel / Rules when *obj* is an interface."""
    parent = get_interface_parent_host(obj)
    if parent is None or not getattr(parent, "pk", None):
        return {}
    url = parent.get_absolute_url() if hasattr(parent, "get_absolute_url") else ""
    if not url:
        return {}
    return {
        "parent_url": url,
        "parent_name": str(parent),
    }
