"""Data migration helpers for NSM 0.4.2 storage consolidation."""

from __future__ import annotations


def migrate_typeconfig_and_sections_to_comments(apps) -> int:
    """Merge legacy TypeConfig + Section M2M into COT ``comments``."""
    from netbox_nsm.objects.nsm_config import (
        config_dict_from_typeconfig,
        merge_nsm_config_document_into_comments,
        parse_nsm_config_from_comments,
    )

    try:
        TypeConfig = apps.get_model("netbox_nsm", "TypeConfig")
        Section = apps.get_model("netbox_nsm", "Section")
        CustomObjectType = apps.get_model("netbox_custom_objects", "CustomObjectType")
    except LookupError:
        return 0

    slug_areas: dict[str, list[str]] = {}
    for section in Section.objects.all():
        for cot in section.custom_object_types.all():
            slug_areas.setdefault(cot.slug, [])
            if section.slug not in slug_areas[cot.slug]:
                slug_areas[cot.slug].append(section.slug)

    updated = 0
    for tc in TypeConfig.objects.select_related("content_type").all():
        ct = tc.content_type
        if ct.app_label != "netbox_custom_objects":
            continue
        cot = CustomObjectType.objects.filter(pk=ct.pk).first()
        if cot is None:
            import re

            match = re.match(r"table(\d+)model", ct.model, re.I)
            if match:
                cot = CustomObjectType.objects.filter(pk=int(match.group(1))).first()
        if cot is None:
            continue

        base = parse_nsm_config_from_comments(cot.comments or "") or {}
        legacy = config_dict_from_typeconfig(tc)
        merged_doc = {
            "rule_view": {
                "sort_order": legacy.get("sort_order", base.get("sort_order", 0)),
                "display_template": legacy.get(
                    "display_template", base.get("display_template", "{name}")
                ),
                "areas": slug_areas.get(cot.slug, base.get("areas", [])),
            },
            "panel": legacy.get("panel") or base.get("panel"),
            "object_builder": base.get("object_builder"),
            "rulebook": base.get("rulebook"),
        }
        new_comments = merge_nsm_config_document_into_comments(
            cot.comments or "",
            merged_doc,
        ).rstrip()
        if cot.comments != new_comments:
            cot.comments = new_comments
            cot.save(update_fields=["comments"])
            updated += 1
    return updated


def migrate_cot_rulebook_assignments_to_object_links(apps) -> tuple[int, int]:
    """Copy ``CotRulebookAssignment`` rows into ``nsm_object_link`` COT instances."""
    from netbox_nsm.objects.object_link_service import (
        LINK_TYPE_RULEBOOK,
        find_rulebook_link,
        get_object_link_model,
        link_name_for_rulebook,
    )

    try:
        CotRulebookAssignment = apps.get_model("netbox_nsm", "CotRulebookAssignment")
    except LookupError:
        return 0, 0

    model = get_object_link_model()
    if model is None:
        return 0, 0

    created = 0
    skipped = 0
    for assignment in CotRulebookAssignment.objects.select_related(
        "assigned_object_type"
    ).iterator():
        host = assignment.assigned_object
        if host is None:
            try:
                host = assignment.assigned_object_type.get_object_for_this_type(
                    pk=assignment.assigned_object_id
                )
            except Exception:
                skipped += 1
                continue
        slug = (assignment.cot_slug or "").strip()
        if not slug:
            skipped += 1
            continue
        if find_rulebook_link(host, slug) is not None:
            skipped += 1
            continue
        comment = (assignment.description or "").strip()
        model.objects.create(
            name=link_name_for_rulebook(host, slug),
            link_type=LINK_TYPE_RULEBOOK,
            netbox_object=host,
            rulebook_slug=slug,
            comment=comment,
        )
        created += 1
    return created, skipped


def run_storage_consolidation(apps) -> None:
    migrate_typeconfig_and_sections_to_comments(apps)
    migrate_cot_rulebook_assignments_to_object_links(apps)
