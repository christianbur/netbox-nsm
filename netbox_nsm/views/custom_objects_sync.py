"""Sync netbox_nsm built-in types into netbox-custom-objects.

Triggered from Setup (full sync button). Performs three
phases inside a single atomic transaction:

1. Ensure all required ``extras.CustomFieldChoiceSet`` instances exist.
2. Apply the portable schema document via ``apply_document``.
3. Seed each type's ``default_objects`` via the generated dynamic model.
"""

from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View

from netbox_nsm.builtin_types import BUILTIN_CUSTOM_TYPES
from django.http import Http404

from netbox_nsm.setup_flags import setup_allow_destructive_actions, setup_menu_enabled
from netbox_nsm.custom_objects_schema import (
    build_choice_set_specs,
    build_schema_document,
    iter_types,
    slugify_identifier,
)
from netbox_nsm.models import Section, TypeConfig
from netbox_nsm.panel_sections import section_slugs_to_panel_slugs
from netbox_nsm.type_config_specs import TYPECONFIG_SPEC_BY_SLUG

__all__ = ("SyncBuiltinToCustomObjectsView", "SyncTypeConfigsView")


_AREA_ORDER = {"srcdst": 10, "services": 30, "action": 40, "info": 50}


def _prune_stale(document):
    """Drop CustomObjectTypes / Sections left over from earlier sync runs.

    Removes any ``CustomObjectType`` whose slug starts with ``nsm_`` but is not
    in the current document, and any ``Section`` whose slug isn't one of
    the current group_names.
    """
    from netbox_custom_objects.models import CustomObjectType

    wanted_cot_slugs = {t["slug"] for t in document["types"]}
    wanted_area_slugs = {
        t["group_name"] for t in document["types"] if t.get("group_name")
    }

    stale_cots = CustomObjectType.objects.exclude(slug__in=wanted_cot_slugs)
    cots_removed = stale_cots.count()
    stale_cots.delete()

    stale_sections = Section.objects.exclude(slug__in=wanted_area_slugs)
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
    """Populate TypeConfig (display_template, panel_slugs) and Section (M2M) tables."""
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
        section, _ = Section.objects.update_or_create(
            slug=area,
            defaults={
                "name": area.replace("_", " ").replace("-", " ").title(),
                "sort_order": _AREA_ORDER.get(area, 100),
            },
        )
        section_by_slug[area] = section

    # One COT per typedef; attach TypeConfig and add to each area section.
    for typedef, _base_slug, slug, areas in iter_types(builtin_types):
        try:
            cot = CustomObjectType.objects.get(slug=slug)
        except CustomObjectType.DoesNotExist:
            continue

        from django.contrib.contenttypes.models import ContentType as DjContentType

        ct = DjContentType.objects.get_for_model(cot.get_model())

        spec = TYPECONFIG_SPEC_BY_SLUG.get(slug)
        panel_slugs = (
            spec["panel_slugs"] if spec else section_slugs_to_panel_slugs(areas)
        )
        matching_class = spec["matching_class"] if spec else ""
        TypeConfig.objects.update_or_create(
            content_type=ct,
            matching_class=matching_class,
            defaults={
                "name": spec["label"] if spec else str(typedef.get("name", "") or slug),
                "display_template": str(
                    (spec or typedef).get("display_template", "") or ""
                ),
                "order_id": int((spec or typedef).get("order_id", 100) or 100),
                "panel_slugs": panel_slugs,
                "panel_linkable": (spec or {}).get("panel_linkable", True),
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
        if not setup_menu_enabled():
            raise Http404
        redirect_url = reverse("plugins:netbox_nsm:setup")

        if not setup_allow_destructive_actions():
            messages.error(
                request,
                _("Full sync is disabled (setup_allow_destructive_actions)."),
            )
            return redirect(redirect_url)

        try:
            from netbox_custom_objects.schema.executor import apply_document
        except ImportError:
            messages.error(
                request,
                _("Plugin netbox_custom_objects is not installed."),
            )
            return redirect(redirect_url)

        choice_specs = build_choice_set_specs(BUILTIN_CUSTOM_TYPES)
        document = build_schema_document(BUILTIN_CUSTOM_TYPES)

        try:
            with transaction.atomic():
                cs_created, cs_kept = _ensure_choice_sets(choice_specs)
                apply_document(document, allow_destructive=True)
                cots_pruned, secs_pruned = _prune_stale(document)
                obj_created, obj_updated, obj_skipped = _seed_default_objects(
                    BUILTIN_CUSTOM_TYPES
                )
        except Exception as exc:
            messages.error(
                request,
                _("Sync failed: %(exc_type)s: %(exc)s")
                % {"exc_type": exc.__class__.__name__, "exc": exc},
            )
            return redirect(redirect_url)

        messages.success(
            request,
            _(
                "Custom Object Types synced — %(types)d types, %(cs_created)d new "
                "ChoiceSets (%(cs_kept)d existing), %(obj_created)d new objects, "
                "%(obj_updated)d updated, %(obj_skipped)d skipped, "
                "%(cots_pruned)d old types + %(secs_pruned)d old sections removed. "
                "Run TypeConfig sync (step 2) separately."
            )
            % {
                "types": len(document["types"]),
                "cs_created": cs_created,
                "cs_kept": cs_kept,
                "obj_created": obj_created,
                "obj_updated": obj_updated,
                "obj_skipped": obj_skipped,
                "cots_pruned": cots_pruned,
                "secs_pruned": secs_pruned,
            },
        )
        return redirect(redirect_url)


class SyncTypeConfigsView(LoginRequiredMixin, View):
    """POST-only: TypeConfigs + NSM sections from built-in type specs."""

    def post(self, request, *args, **kwargs):
        if not setup_menu_enabled():
            raise Http404
        redirect_url = reverse("plugins:netbox_nsm:setup")

        if not setup_allow_destructive_actions():
            messages.error(
                request,
                _("TypeConfig sync is disabled (setup_allow_destructive_actions)."),
            )
            return redirect(redirect_url)

        try:
            from netbox_custom_objects.models import CustomObjectType  # noqa: F401
        except ImportError:
            messages.error(
                request,
                _("Plugin netbox_custom_objects is not installed."),
            )
            return redirect(redirect_url)

        try:
            with transaction.atomic():
                cfg_count, sec_links = _sync_type_configs_and_sections(
                    BUILTIN_CUSTOM_TYPES
                )
        except Exception as exc:
            messages.error(
                request,
                _("TypeConfig sync failed: %(exc_type)s: %(exc)s")
                % {"exc_type": exc.__class__.__name__, "exc": exc},
            )
            return redirect(redirect_url)

        messages.success(
            request,
            _(
                "TypeConfig sync complete — %(cfg_count)d TypeConfigs, "
                "%(sec_links)d section links."
            )
            % {"cfg_count": cfg_count, "sec_links": sec_links},
        )
        return redirect(redirect_url)
