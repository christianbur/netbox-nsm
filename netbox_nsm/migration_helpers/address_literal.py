"""Migrate ``network_literal`` COT field data into instance ``comments``."""

from __future__ import annotations

import re

__all__ = ("migrate_network_literal_to_comments",)

_PLAIN_CIDR_RE = re.compile(
    r"^\s*((?:\d{1,3}\.){3}\d{1,3}/\d{1,2})\s*$"
)


def migrate_network_literal_to_comments() -> int:
    """Move ``network_literal`` field values (and legacy plain-CIDR comments) to ``nsm_config``."""
    from netbox_nsm.objects.address_literal import (
        merge_network_into_instance_comments,
        parse_network_from_instance_comments,
    )

    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return 0

    cot = CustomObjectType.objects.filter(slug="nsm_address").first()
    if cot is None:
        return 0

    model = cot.get_model()
    updated = 0

    for obj in model.objects.all().iterator():
        comments = (obj.comments or "").strip()
        field_value = getattr(obj, "network_literal", None)
        field_literal = str(field_value).strip() if field_value else ""

        existing_network = parse_network_from_instance_comments(comments)
        plain_match = (
            _PLAIN_CIDR_RE.match(comments)
            if comments and "nsm_config" not in comments
            else None
        )
        plain_literal = plain_match.group(1) if plain_match else ""

        network = existing_network or field_literal or plain_literal
        if not network:
            if field_literal:
                obj.network_literal = ""
                obj.save(update_fields=["network_literal"])
                updated += 1
            continue

        new_comments = merge_network_into_instance_comments(comments, network)
        update_fields: list[str] = []
        if new_comments != (obj.comments or ""):
            obj.comments = new_comments
            update_fields.append("comments")
        if field_literal:
            obj.network_literal = ""
            update_fields.append("network_literal")
        if update_fields:
            obj.save(update_fields=update_fields)
            updated += 1

    return updated
