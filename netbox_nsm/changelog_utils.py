"""
Helpers for NetBox ObjectChange / changelog integration in netbox_nsm.

Junction-table writes (rule assignments, grid inline edits) bypass a normal
``Rule.save()`` and therefore need an explicit changelog entry on the parent.
"""

from __future__ import annotations

from core.choices import ObjectChangeActionChoices
from netbox.context import current_request
from netbox_nsm.models.rulebook import (
    _group_item_changelog_key,
    _object_item_changelog_key,
)
from netbox_nsm.models.type_config import PANEL_LINKABLE_DISABLED


def _layout_as_map(layout):
    """Normalize fields_layout snapshots (legacy list or slug-keyed dict)."""
    if isinstance(layout, dict):
        return layout
    if isinstance(layout, list):
        return {
            row["slug"]: row
            for row in layout
            if isinstance(row, dict) and row.get("slug")
        }
    return {}


def describe_rulebook_fields_layout_changes(prechange, postchange):
    """Human-readable summary for Rulebook field-layout edits."""
    pre_layout = _layout_as_map((prechange or {}).get("fields_layout"))
    post_layout = _layout_as_map((postchange or {}).get("fields_layout"))
    lines = []

    for slug in sorted(set(pre_layout) | set(post_layout)):
        old = pre_layout.get(slug)
        new = post_layout.get(slug)
        if old == new:
            continue
        label = (new or old or {}).get("name") or slug
        if old is None:
            lines.append(f'Added field "{label}" ({slug})')
            continue
        if new is None:
            lines.append(f'Removed field "{label}" ({slug})')
            continue
        for key in sorted(set(old) | set(new)):
            if old.get(key) == new.get(key):
                continue
            if key == "types" and isinstance(old.get(key), dict) and isinstance(
                new.get(key), dict
            ):
                for tc_id in sorted(set(old["types"]) | set(new["types"])):
                    old_type = old["types"].get(tc_id)
                    new_type = new["types"].get(tc_id)
                    if old_type == new_type:
                        continue
                    if old_type is None:
                        lines.append(
                            f'Field "{label}": added type config {tc_id}'
                        )
                    elif new_type is None:
                        lines.append(
                            f'Field "{label}": removed type config {tc_id}'
                        )
                    else:
                        for tkey in sorted(set(old_type) | set(new_type)):
                            if old_type.get(tkey) != new_type.get(tkey):
                                lines.append(
                                    f'Field "{label}" type {tc_id}: '
                                    f"{tkey} {old_type.get(tkey)!r} → "
                                    f"{new_type.get(tkey)!r}"
                                )
                continue
            lines.append(
                f'Field "{label}": {key} {old.get(key)!r} → {new.get(key)!r}'
            )

    return "; ".join(lines)


def _object_items_as_map(items):
    if isinstance(items, dict):
        return items
    if isinstance(items, list):
        mapped = {}
        for row in items:
            if not isinstance(row, dict):
                continue
            key = _object_item_changelog_key(
                row.get("field"),
                row.get("content_type"),
                row.get("object_id"),
            )
            mapped[key] = row
        return mapped
    return {}


def _group_items_as_map(items):
    if isinstance(items, dict):
        return items
    if isinstance(items, list):
        mapped = {}
        for row in items:
            if not isinstance(row, dict):
                continue
            group_id = row.get("security_group_id")
            if group_id is None and row.get("security_group"):
                key = f"{row.get('field') or ''}:grp:{row.get('security_group')}"
            else:
                key = _group_item_changelog_key(row.get("field"), group_id)
            mapped[key] = row
        return mapped
    return {}


def _describe_item_map_changes(pre_map, post_map, *, added_label, removed_label):
    lines = []
    for key in sorted(set(pre_map) | set(post_map)):
        old = pre_map.get(key)
        new = post_map.get(key)
        if old == new:
            continue
        if old is None:
            lines.append(f"{added_label} {key}")
            continue
        if new is None:
            lines.append(f"{removed_label} {key}")
            continue
        for attr in sorted(set(old) | set(new)):
            if old.get(attr) != new.get(attr):
                lines.append(
                    f"{key}: {attr} {old.get(attr)!r} → {new.get(attr)!r}"
                )
    return lines


def describe_rule_assignment_changes(prechange, postchange):
    """Human-readable summary for rule editor / grid assignment edits."""
    lines = []
    lines.extend(
        _describe_item_map_changes(
            _object_items_as_map((prechange or {}).get("object_items")),
            _object_items_as_map((postchange or {}).get("object_items")),
            added_label="Added object",
            removed_label="Removed object",
        )
    )
    lines.extend(
        _describe_item_map_changes(
            _group_items_as_map((prechange or {}).get("group_items")),
            _group_items_as_map((postchange or {}).get("group_items")),
            added_label="Added group",
            removed_label="Removed group",
        )
    )
    pre_vg = (prechange or {}).get("virtual_group_config")
    post_vg = (postchange or {}).get("virtual_group_config")
    if pre_vg != post_vg:
        lines.append(
            f"virtual_group_config {pre_vg!r} → {post_vg!r}"
        )
    return "; ".join(lines)


def _rules_layout_as_map(layout):
    if isinstance(layout, dict):
        return layout
    return {}


def _field_slug_label(slug):
    if not slug:
        return "?"
    return str(slug).replace("_", " ").replace("-", " ").title()


def _object_item_label(row):
    if not isinstance(row, dict):
        return "?"
    field = _field_slug_label(row.get("field"))
    ct_id = row.get("content_type")
    object_id = row.get("object_id")
    display = f"#{object_id}"
    if ct_id and object_id:
        try:
            from django.contrib.contenttypes.models import ContentType

            ct = ContentType.objects.get_for_id(int(ct_id))
            obj = ct.get_object_for_this_type(pk=int(object_id))
            display = str(obj)
        except Exception:
            pass
    exclude = row.get("exclude")
    suffix = " (exclude)" if exclude else ""
    return f"{field}: {display}{suffix}"


def _group_item_label(row):
    if not isinstance(row, dict):
        return "?"
    field = _field_slug_label(row.get("field"))
    name = row.get("security_group") or row.get("security_group_id")
    exclude = row.get("exclude")
    suffix = " (exclude)" if exclude else ""
    return f"{field}: {name}{suffix}"


def _describe_rule_items_changes(rule_label, old_items, new_items, *, kind):
    lines = []
    if kind == "object":
        label_fn = _object_item_label
    else:
        label_fn = _group_item_label
    for key in sorted(set(old_items) | set(new_items)):
        old = old_items.get(key)
        new = new_items.get(key)
        if old == new:
            continue
        if old is None:
            lines.append(f'Rule "{rule_label}": added {label_fn(new)}')
        elif new is None:
            lines.append(f'Rule "{rule_label}": removed {label_fn(old)}')
        else:
            lines.append(
                f'Rule "{rule_label}": updated {label_fn(new)}'
            )
    return lines


def describe_rulebook_rules_changes(prechange, postchange):
    """Human-readable summary for Rulebook rule / assignment edits."""
    pre_rules = _rules_layout_as_map((prechange or {}).get("rules_layout"))
    post_rules = _rules_layout_as_map((postchange or {}).get("rules_layout"))
    lines = []

    for rule_id in sorted(set(pre_rules) | set(post_rules), key=lambda x: (len(x), x)):
        old = pre_rules.get(rule_id)
        new = post_rules.get(rule_id)
        if old == new:
            continue
        label = (new or old or {}).get("name") or f"#{rule_id}"
        if old is None:
            lines.append(f'Added rule "{label}"')
            continue
        if new is None:
            lines.append(f'Removed rule "{label}"')
            continue
        for attr in ("name", "index", "enabled"):
            if old.get(attr) != new.get(attr):
                lines.append(
                    f'Rule "{label}": {attr} {old.get(attr)!r} → {new.get(attr)!r}'
                )
        lines.extend(
            _describe_rule_items_changes(
                label,
                old.get("object_items") or {},
                new.get("object_items") or {},
                kind="object",
            )
        )
        lines.extend(
            _describe_rule_items_changes(
                label,
                old.get("group_items") or {},
                new.get("group_items") or {},
                kind="group",
            )
        )

    return "; ".join(lines)


def _panel_slugs_as_map(slugs):
    if isinstance(slugs, dict):
        return slugs
    if isinstance(slugs, list):
        return {slug: True for slug in slugs if slug}
    return {}


def _panel_linkable_types_as_map(type_ids):
    if isinstance(type_ids, dict):
        return type_ids
    if type_ids == [PANEL_LINKABLE_DISABLED]:
        return {"__disabled__": True}
    if isinstance(type_ids, list):
        return {
            str(int(pk)): int(pk)
            for pk in type_ids
            if int(pk) != PANEL_LINKABLE_DISABLED
        }
    return {}


def describe_type_config_changes(prechange, postchange):
    """Human-readable summary for TypeConfig panel slug / linkable-type edits."""
    lines = []
    pre_slugs = _panel_slugs_as_map((prechange or {}).get("panel_slugs"))
    post_slugs = _panel_slugs_as_map((postchange or {}).get("panel_slugs"))
    for slug in sorted(set(pre_slugs) | set(post_slugs)):
        if slug in pre_slugs and slug not in post_slugs:
            lines.append(f'Removed panel slug "{slug}"')
        elif slug not in pre_slugs and slug in post_slugs:
            lines.append(f'Added panel slug "{slug}"')

    pre_link = _panel_linkable_types_as_map(
        (prechange or {}).get("panel_linkable_types")
    )
    post_link = _panel_linkable_types_as_map(
        (postchange or {}).get("panel_linkable_types")
    )
    if pre_link.get("__disabled__") != post_link.get("__disabled__"):
        if post_link.get("__disabled__"):
            lines.append("Panel linking disabled")
        else:
            lines.append("Panel linking enabled")
    for key in sorted(set(pre_link) | set(post_link)):
        if key == "__disabled__":
            continue
        if key in pre_link and key not in post_link:
            lines.append(f"Removed linkable type {key}")
        elif key not in pre_link and key in post_link:
            lines.append(f"Added linkable type {key}")

    return "; ".join(lines)


def apply_type_config_changelog_message(instance, *, prechange=None):
    """Set ``_changelog_message`` on TypeConfig before save when panel fields changed."""
    prechange = prechange or getattr(instance, "_prechange_snapshot", None)
    if not prechange:
        return
    message = describe_type_config_changes(prechange, snapshot_instance(instance))
    if message:
        instance._changelog_message = message


def snapshot_instance(instance, *, exclude=None):
    """Return serialized state for manual pre/post change logging."""
    if hasattr(instance, "serialize_object"):
        return instance.serialize_object(exclude=exclude or ["last_updated"])
    return None


def record_object_update(instance, request, prechange_data, *, message=""):
    """
    Persist an ObjectChange for *instance* when data changed outside ``save()``.

    Used after bulk junction-table writes so the parent object's changelog
    reflects assignment changes (Rule object/group items, etc.).
    """
    req = request or current_request.get()
    if req is None:
        return

    instance._prechange_snapshot = prechange_data
    instance._changelog_message = message or ""
    objectchange = instance.to_objectchange(ObjectChangeActionChoices.ACTION_UPDATE)
    if not objectchange.has_changes:
        return

    objectchange.user = req.user
    objectchange.request_id = req.id
    objectchange.save()


def snapshot_before_edit(instance):
    """Take a pre-change snapshot when editing via custom views (not ObjectEditView)."""
    if instance.pk and hasattr(instance, "snapshot"):
        instance.snapshot()


def record_rulebook_layout_changelog(rulebook, request, prechange, *, message=""):
    """Write field-layout changes to the parent Rulebook changelog."""
    if not message:
        postchange = snapshot_instance(rulebook)
        message = describe_rulebook_fields_layout_changes(prechange, postchange)
    record_object_update(rulebook, request, prechange, message=message)


def rulebook_rules_data_changed(prechange, postchange):
    if not prechange or not postchange:
        return False
    return prechange.get("rules_layout") != postchange.get("rules_layout")


def record_rulebook_rules_changelog(rulebook, request, prechange, *, message=""):
    """Write rule / assignment changes to the parent Rulebook changelog."""
    if not prechange:
        return
    postchange = snapshot_instance(rulebook)
    if not rulebook_rules_data_changed(prechange, postchange):
        return
    if not message:
        message = describe_rulebook_rules_changes(prechange, postchange)
    record_object_update(rulebook, request, prechange, message=message)


def rule_assignment_data_changed(prechange, postchange):
    """True when rule editor object/group selections changed."""
    if not prechange or not postchange:
        return False
    for key in ("object_items", "group_items", "virtual_group_config"):
        if prechange.get(key) != postchange.get(key):
            return True
    return False


def record_rule_assignment_changelog(rule, request, prechange, *, message=""):
    """Write picker assignment changes to the Rule changelog."""
    if not prechange:
        return
    postchange = snapshot_instance(rule)
    if not rule_assignment_data_changed(prechange, postchange):
        return
    if not message:
        message = describe_rule_assignment_changes(prechange, postchange)
    record_object_update(rule, request, prechange, message=message)
