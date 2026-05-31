"""Sync netbox_nsm built-in types into netbox-custom-objects.

Triggered from the Object-Builder Types tab via a button. Performs three
phases inside a single atomic transaction:

1. Ensure all required ``extras.CustomFieldChoiceSet`` instances exist.
2. Apply the portable schema document via ``apply_document``.
3. Seed each type's ``default_objects`` via the generated dynamic model.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View

from netbox_nsm.builtin_types import BUILTIN_CUSTOM_TYPES
from netbox_nsm.custom_objects_schema import (
    build_choice_set_specs,
    build_schema_document,
    iter_types,
    slugify_identifier,
)
from netbox_nsm.models import NSMSection, NSMTypeConfig

__all__ = ("SyncBuiltinToCustomObjectsView",)


_AREA_ORDER = {"srcdst": 10, "services": 30, "action": 40, "info": 50}


def _prune_stale(document):
    """Drop CustomObjectTypes / NSMSections left over from earlier sync runs.

    Removes any ``CustomObjectType`` whose slug starts with ``nsm_`` but is not
    in the current document, and any ``NSMSection`` whose slug isn't one of
    the current group_names.
    """
    from netbox_custom_objects.models import CustomObjectType

    wanted_cot_slugs = {t["slug"] for t in document["types"]}
    wanted_area_slugs = {t["group_name"] for t in document["types"] if t.get("group_name")}

    stale_cots = CustomObjectType.objects.exclude(slug__in=wanted_cot_slugs)
    cots_removed = stale_cots.count()
    stale_cots.delete()

    stale_sections = NSMSection.objects.exclude(slug__in=wanted_area_slugs)
    sections_removed = stale_sections.count()
    stale_sections.delete()

    return cots_removed, sections_removed


def _ensure_choice_sets(specs):
    """Create missing ``CustomFieldChoiceSet`` rows. Returns ``(created, kept)``."""
    from extras.models import CustomFieldChoiceSet

    created = 0
    kept = 0
    for spec in specs:
        extra_choices = [(c, c) for c in spec["choices"]]
        obj, was_created = CustomFieldChoiceSet.objects.update_or_create(
            name=spec["name"],
            defaults={"extra_choices": extra_choices},
        )
        if was_created:
            created += 1
        else:
            kept += 1
    return created, kept


def _seed_default_objects(builtin_types):
    """Iterate types and seed their default objects."""
    from netbox_custom_objects.models import CustomObjectType

    created = 0
    updated = 0
    skipped = 0

    for typedef, _base_slug, slug, _areas in iter_types(builtin_types):
        defaults_list = typedef.get("default_objects") or []
        if not defaults_list:
            continue

        try:
            cot = CustomObjectType.objects.get(slug=slug)
        except CustomObjectType.DoesNotExist:
            skipped += len(defaults_list)
            continue

        model = cot.get_model()
        for entry in defaults_list:
            if not isinstance(entry, dict):
                skipped += 1
                continue
            obj_name = str(entry.get("name", "")).strip()
            if not obj_name:
                skipped += 1
                continue

            payload = {"name": obj_name}
            for k, v in (entry.get("field_data") or {}).items():
                payload[slugify_identifier(k)] = v

            try:
                _, was_created = model.objects.update_or_create(
                    name=obj_name, defaults=payload
                )
            except Exception:
                skipped += 1
                continue
            if was_created:
                created += 1
            else:
                updated += 1

    return created, updated, skipped


def _sync_type_configs_and_sections(builtin_types):
    """Populate NSMTypeConfig (display_template) and NSMSection (M2M) tables."""
    from netbox_custom_objects.models import CustomObjectType

    sections_touched = 0
    configs_touched = 0

    # Collect all referenced areas (already collapsed) and (re)create sections.
    referenced_areas = []
    for _td, _bs, _slug, areas in iter_types(builtin_types):
        for a in areas:
            if a not in referenced_areas:
                referenced_areas.append(a)

    section_by_slug = {}
    for area in referenced_areas:
        section, _ = NSMSection.objects.update_or_create(
            slug=area,
            defaults={
                "name": area.replace("_", " ").replace("-", " ").title(),
                "sort_order": _AREA_ORDER.get(area, 100),
            },
        )
        section_by_slug[area] = section

    # One COT per typedef; attach NSMTypeConfig and add to each area section.
    for typedef, _base_slug, slug, areas in iter_types(builtin_types):
        try:
            cot = CustomObjectType.objects.get(slug=slug)
        except CustomObjectType.DoesNotExist:
            continue

        from django.contrib.contenttypes.models import ContentType as DjContentType
        ct = DjContentType.objects.get_for_model(cot.get_model())

        NSMTypeConfig.objects.update_or_create(
            content_type=ct,
            defaults={
                "display_template": str(typedef.get("display_template", "") or ""),
                "order_id": int(typedef.get("order_id", 100) or 100),
            },
        )
        configs_touched += 1

        for area in areas:
            sec = section_by_slug.get(area)
            if sec:
                sec.custom_object_types.add(cot)
                sections_touched += 1

    return configs_touched, sections_touched


class SyncBuiltinToCustomObjectsView(LoginRequiredMixin, View):
    """POST-only: full sync of BUILTIN_CUSTOM_TYPES into custom-objects."""

    def post(self, request, *args, **kwargs):
        redirect_url = reverse(
            "plugins:netbox_nsm:object_builder", args=["types"]
        )

        try:
            from netbox_custom_objects.schema.executor import apply_document
        except ImportError:
            messages.error(
                request, "Plugin netbox_custom_objects ist nicht installiert."
            )
            return redirect(redirect_url)

        choice_specs = build_choice_set_specs(BUILTIN_CUSTOM_TYPES)
        document = build_schema_document(BUILTIN_CUSTOM_TYPES)

        try:
            with transaction.atomic():
                cs_created, cs_kept = _ensure_choice_sets(choice_specs)
                apply_document(document, allow_destructive=True)
                cots_pruned, secs_pruned = _prune_stale(document)
                cfg_count, sec_links = _sync_type_configs_and_sections(
                    BUILTIN_CUSTOM_TYPES
                )
                obj_created, obj_updated, obj_skipped = _seed_default_objects(
                    BUILTIN_CUSTOM_TYPES
                )
        except Exception as exc:
            messages.error(
                request,
                f"Sync fehlgeschlagen: {exc.__class__.__name__}: {exc}",
            )
            return redirect(redirect_url)

        messages.success(
            request,
            (
                f"Sync ok — {len(document['types'])} CustomObjectTypes, "
                f"{cs_created} neue ChoiceSets ({cs_kept} bestehend), "
                f"{cfg_count} TypeConfigs, {sec_links} Section-Verknüpfungen, "
                f"{obj_created} neue Objekte, {obj_updated} aktualisiert, "
                f"{obj_skipped} übersprungen, "
                f"{cots_pruned} alte Types + {secs_pruned} alte Sections entfernt."
            ),
        )
        return redirect(redirect_url)
