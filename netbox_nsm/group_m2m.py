"""
Shared helpers for Custom Object ``group`` M2M fields (e.g. nsm_addresses, nsm_services).

Used by the Security Panel and Object Analyzer so both show the same membership edges.
"""

from __future__ import annotations

__all__ = (
    "GROUP_M2M_LABEL_MEMBER",
    "GROUP_M2M_LABEL_MEMBER_OF",
    "iter_group_m2m_relations",
)

GROUP_M2M_LABEL_MEMBER = "Member"
GROUP_M2M_LABEL_MEMBER_OF = "Member of"


def iter_group_m2m_relations(obj):
    """
    Yield ``(related_object, label)`` for both directions of a ``group`` M2M field:

    - **Member of** — parent groups that contain *obj* (reverse: ``filter(group=obj)``)
    - **Member** — objects contained in *obj* when it acts as a group (forward: ``obj.group.all()``)
    """
    group_rel = getattr(obj, "group", None)
    if group_rel is None or not hasattr(group_rel, "all"):
        return

    Model = type(obj)

    try:
        for parent in Model.objects.filter(group=obj).order_by("name"):
            yield parent, GROUP_M2M_LABEL_MEMBER_OF
    except Exception:
        pass

    try:
        for member in group_rel.all().order_by("name"):
            if member.pk == obj.pk:
                continue
            yield member, GROUP_M2M_LABEL_MEMBER
    except Exception:
        pass
