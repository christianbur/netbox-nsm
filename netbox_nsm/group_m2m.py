"""
Shared helpers for Custom Object ``group`` M2M fields (e.g. nsm_addresses, nsm_services).

Used by the Security Panel and Object Analyzer so both show the same membership edges.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    "GROUP_M2M_LABEL_MEMBER",
    "GROUP_M2M_LABEL_MEMBER_OF",
    "GroupM2mRelation",
    "group_m2m_panel_type_key",
    "group_m2m_panel_type_label",
    "iter_group_m2m_relations",
    "iter_object_group_memberships",
)

GROUP_M2M_LABEL_MEMBER = "Member"
GROUP_M2M_LABEL_MEMBER_OF = "Member of"


@dataclass(frozen=True)
class GroupM2mRelation:
    related: object
    label: str
    via: str | None = None
    remove_group: object | None = None
    remove_member: object | None = None


def group_m2m_panel_type_key(base_type_key: str, label: str) -> str:
    """Separate panel sections for member-of vs member side."""
    if label == GROUP_M2M_LABEL_MEMBER_OF:
        return f"{base_type_key}__member_of"
    return f"{base_type_key}__member"


def group_m2m_panel_type_label(base_label: str, label: str) -> str:
    if label == GROUP_M2M_LABEL_MEMBER_OF:
        return f"{base_label} — Member of"
    return f"{base_label} — Member"


def iter_group_m2m_relations(obj):
    """
    Yield group M2M relations for Custom Objects with a ``group`` field.

    - **Member of** — parent group(s) containing *obj*
    - **Member** — objects in *obj* when it acts as a group
    - **Member** (peers) — other members of the same parent group(s), so members
      are visible from both the group object and each member object
    """
    group_rel = getattr(obj, "group", None)
    if group_rel is None or not hasattr(group_rel, "all"):
        return

    Model = type(obj)
    parents: list = []

    try:
        parents = list(Model.objects.filter(group=obj).order_by("name"))
        for parent in parents:
            yield GroupM2mRelation(
                parent,
                GROUP_M2M_LABEL_MEMBER_OF,
                remove_group=parent,
                remove_member=obj,
            )
    except Exception:
        pass

    seen_member_pks = {obj.pk}

    try:
        for member in group_rel.all().order_by("name"):
            if member.pk in seen_member_pks:
                continue
            seen_member_pks.add(member.pk)
            yield GroupM2mRelation(
                member,
                GROUP_M2M_LABEL_MEMBER,
                remove_group=obj,
                remove_member=member,
            )
    except Exception:
        pass

    try:
        for parent in parents:
            parent_members = parent.group.all().order_by("name")
            for peer in parent_members:
                if peer.pk in seen_member_pks:
                    continue
                seen_member_pks.add(peer.pk)
                yield GroupM2mRelation(
                    peer,
                    GROUP_M2M_LABEL_MEMBER,
                    via=str(parent),
                    remove_group=parent,
                    remove_member=peer,
                )
    except Exception:
        pass


def iter_object_group_memberships(obj):
    """
    Yield NSM ObjectGroup membership (Security Object Groups).

    - **Member of** — ObjectGroups that contain *obj*
    - **Member** — members when *obj* is an ObjectGroup (incl. sub-groups)
    """
    from django.contrib.contenttypes.models import ContentType

    from netbox_nsm.models import ObjectGroup, ObjectGroupMember

    try:
        ct = ContentType.objects.get_for_model(obj)
        for row in (
            ObjectGroupMember.objects.filter(content_type=ct, object_id=obj.pk)
            .select_related("group")
            .order_by("group__name")
        ):
            if row.group_id:
                yield GroupM2mRelation(row.group, GROUP_M2M_LABEL_MEMBER_OF)
    except Exception:
        pass

    if not isinstance(obj, ObjectGroup):
        return

    try:
        for row in (
            ObjectGroupMember.objects.filter(group=obj)
            .select_related("content_type")
            .order_by("content_type__app_label", "content_type__model", "object_id")
        ):
            assigned = row.assigned_object
            if assigned is not None:
                yield GroupM2mRelation(assigned, GROUP_M2M_LABEL_MEMBER)
    except Exception:
        pass

    try:
        for sub in obj.sub_groups.all().order_by("name"):
            yield GroupM2mRelation(sub, GROUP_M2M_LABEL_MEMBER, via=str(obj))
    except Exception:
        pass
