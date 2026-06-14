from __future__ import annotations

from netbox_nsm.query.engine import RulebookContext

from netbox_nsm.rulebooks.grid.layout import _layout_object_columns

def build_filter_column_query_map(
    rules_layout: list,
    context: RulebookContext,
) -> dict[str, str]:
    """Map rules table column ids to NSM query field paths (for filter export)."""
    mapping: dict[str, str] = {
        "index": "Index",
        "name": "Name",
        "description": "Description",
        "enabled": "Status",
    }
    for col in _layout_object_columns(rules_layout):
        rb_field = context.get_field(col["area_slug"])
        if rb_field is None:
            continue
        field_name = rb_field.name
        label = (col.get("label") or "").strip()
        if label:
            mapping[col["key"]] = f"{field_name}.{label}.Name"
        else:
            mapping[col["key"]] = f"{field_name}.Name"
    return mapping


def field_path_to_shorthand(field_path: str) -> str:
    """Short display name for a filter column path (e.g. Source.Zones.Name -> Source.Zones)."""
    if field_path == "Rulebook.Name":
        return "Rulebook"
    if field_path in ("Index", "Name", "Description", "Status"):
        return field_path
    if field_path.endswith(".Name") and field_path.count(".") >= 2:
        return field_path.rsplit(".", 1)[0]
    return field_path


def build_filter_column_shorthand_names(
    column_map: dict[str, str],
    rules_layout: list,
) -> dict[str, str]:
    """Map rules table column ids to shorthand names used in filter query export."""
    del rules_layout  # reserved for future label overrides
    return {
        col_id: field_path_to_shorthand(path) for col_id, path in column_map.items()
    }


def build_filter_column_aliases(
    column_map: dict[str, str],
    rules_layout: list,
) -> dict[str, str]:
    """Map lowercase shorthand tokens to full NSM field paths."""
    aliases: dict[str, str] = {}
    ambiguous: set[str] = set()

    def add(name: str, path: str) -> None:
        key = (name or "").strip().lower()
        if not key or key in ambiguous:
            return
        existing = aliases.get(key)
        if existing is not None and existing != path:
            ambiguous.add(key)
            aliases.pop(key, None)
        elif existing is None:
            aliases[key] = path

    for path in column_map.values():
        add(path, path)
        add(field_path_to_shorthand(path), path)

    for col in _layout_object_columns(rules_layout):
        label = (col.get("label") or "").strip()
        path = column_map.get(col["key"])
        if label and path:
            add(label, path)

    return aliases

