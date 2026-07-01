"""COT rulebook rule references for the Security tab (``nsm_rb_*``)."""

from __future__ import annotations

from functools import lru_cache
from types import SimpleNamespace
from typing import Iterator

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.urls import reverse

from netbox_nsm.rulebooks.registry import iter_deployed_cot_rulebooks
from netbox_nsm.security.object_rules import build_cot_rule_name_column_filter_url
from netbox_nsm.rulebooks.virtual_cot import build_virtual_cot_rulebook_row

__all__ = (
    "build_cot_security_rulebook_groups",
    "fetch_cot_security_field_rules",
    "iter_cot_security_rulebook_matches",
    "scan_cot_security_references",
)

FIRST_PAGE_DEFAULT = 30
API_BATCH_DEFAULT = 20


def _panel_rulebook(cot) -> SimpleNamespace:
    virtual = build_virtual_cot_rulebook_row(cot)
    return SimpleNamespace(
        pk=cot.pk,
        slug=cot.slug,
        name=virtual.name,
        get_absolute_url=virtual.get_absolute_url,
        get_rules_tab_url=virtual.get_rules_tab_url,
    )


def _panel_field(cot_field) -> SimpleNamespace:
    return SimpleNamespace(
        pk=cot_field.pk,
        name=cot_field.label or cot_field.name,
        slug=cot_field.name,
    )


class _PanelRule:
    def __init__(self, *, instance, cot_slug: str, name: str):
        self.pk = instance.pk
        self._cot_slug = cot_slug
        self.name = name or str(getattr(instance, "index", instance.pk))
        self._instance = instance

    def get_absolute_url(self):
        return reverse(
            "plugins:netbox_custom_objects:customobject",
            kwargs={"custom_object_type": self._cot_slug, "pk": self.pk},
        )


def _rule_display_name(instance) -> str:
    name = getattr(instance, "name", None)
    if name:
        return str(name)
    index = getattr(instance, "index", None)
    if index is not None:
        return str(index)
    return str(instance.pk)


def _poly_filter_param(field_name: str, content_type: ContentType) -> str:
    return f"{field_name}_{content_type.app_label}_{content_type.model}"


def _through_model(cot_field):
    from django.apps import apps
    from netbox_custom_objects.constants import APP_LABEL

    return apps.get_model(APP_LABEL, cot_field.through_model_name)


def _through_table_source_ids(cot_field, content_type: ContentType, obj_id: int):
    """Return distinct rule PKs referencing ``(content_type, obj_id)`` via M2M through table."""
    through = _through_model(cot_field)
    if cot_field.is_polymorphic:
        return (
            through.objects.filter(
                content_type_id=content_type.pk,
                object_id=obj_id,
            )
            .values_list("source_id", flat=True)
            .distinct()
        )
    return (
        through.objects.filter(target_id=obj_id)
        .values_list("source_id", flat=True)
        .distinct()
    )


def _instances_via_through_table(model, cot_field, content_type: ContentType, obj_id: int):
    source_ids = _through_table_source_ids(cot_field, content_type, obj_id)
    return model.objects.filter(pk__in=source_ids).order_by("index", "pk")


def _count_field_references(model, cot_field, content_type: ContentType, obj_id: int) -> int:
    """Count rule instances referencing ``(content_type, obj_id)`` without loading rule rows."""
    from extras.choices import CustomFieldTypeChoices

    if cot_field.type != CustomFieldTypeChoices.TYPE_MULTIOBJECT:
        return 0
    if not _field_allows_content_type(cot_field, content_type):
        return 0
    try:
        through = _through_model(cot_field)
        if cot_field.is_polymorphic:
            return (
                through.objects.filter(
                    content_type_id=content_type.pk,
                    object_id=obj_id,
                )
                .values("source_id")
                .distinct()
                .count()
            )
        return (
            through.objects.filter(target_id=obj_id)
            .values("source_id")
            .distinct()
            .count()
        )
    except Exception:
        return _instances_for_field(model, cot_field, content_type, obj_id).count()


def _rulebook_unique_reference_count(
    model,
    content_type: ContentType,
    obj_id: int,
    fields_with_counts: list[tuple[object, int]],
) -> int:
    """Distinct rule count across multiple fields in one rulebook."""
    if not fields_with_counts:
        return 0
    if len(fields_with_counts) == 1:
        return fields_with_counts[0][1]
    q = Q()
    for cot_field, count in fields_with_counts:
        if count <= 0:
            continue
        q |= Q(pk__in=_through_table_source_ids(cot_field, content_type, obj_id))
    if not q:
        return 0
    return model.objects.filter(q).distinct().count()


@lru_cache(maxsize=128)
def _matching_security_field_keys(content_type_pk: int) -> tuple[tuple[int, int], ...]:
    """Cached ``(cot_pk, field_pk)`` pairs whose multi-object field accepts *content_type*."""
    from extras.choices import CustomFieldTypeChoices

    content_type = ContentType.objects.get(pk=content_type_pk)
    keys: list[tuple[int, int]] = []
    for cot in iter_deployed_cot_rulebooks():
        for cot_field in cot.fields.filter(
            type=CustomFieldTypeChoices.TYPE_MULTIOBJECT,
        ).order_by("weight", "name"):
            if _field_allows_content_type(cot_field, content_type):
                keys.append((cot.pk, cot_field.pk))
    return tuple(keys)


def _iter_matching_security_fields(content_type: ContentType):
    """Yield ``(cot, cot_field)`` for panel/API lookups (field list cached per content type)."""
    from collections import defaultdict

    from extras.choices import CustomFieldTypeChoices

    keys = _matching_security_field_keys(content_type.pk)
    if not keys:
        return

    keys_by_cot: dict[int, list[int]] = defaultdict(list)
    for cot_pk, field_pk in keys:
        keys_by_cot[cot_pk].append(field_pk)

    for cot in iter_deployed_cot_rulebooks():
        field_pks = keys_by_cot.get(cot.pk)
        if not field_pks:
            continue
        fields = {
            field.pk: field
            for field in cot.fields.filter(
                pk__in=field_pks,
                type=CustomFieldTypeChoices.TYPE_MULTIOBJECT,
            )
        }
        for field_pk in field_pks:
            cot_field = fields.get(field_pk)
            if cot_field is not None:
                yield cot, cot_field


def _field_allows_content_type(cot_field, content_type: ContentType) -> bool:
    from extras.choices import CustomFieldTypeChoices

    if cot_field.type != CustomFieldTypeChoices.TYPE_MULTIOBJECT:
        return False
    if cot_field.is_polymorphic:
        for object_type in cot_field.related_object_types.all():
            if (
                object_type.app_label == content_type.app_label
                and object_type.model == content_type.model
            ):
                return True
        return False
    related = cot_field.related_object_type
    if related is None:
        return False
    return (
        related.app_label == content_type.app_label
        and related.model == content_type.model
    )


def _instances_for_field(model, cot_field, content_type: ContentType, obj_id: int):
    """Return rule instances in *model* that reference ``(content_type, obj_id)``."""
    from extras.choices import CustomFieldTypeChoices

    if cot_field.type != CustomFieldTypeChoices.TYPE_MULTIOBJECT:
        return model.objects.none()
    if not _field_allows_content_type(cot_field, content_type):
        return model.objects.none()

    if cot_field.is_polymorphic:
        try:
            from utilities.filtersets import get_filterset_class

            param = _poly_filter_param(cot_field.name, content_type)
            filterset = get_filterset_class(model)(
                {param: [obj_id]},
                model.objects.all(),
            )
            return filterset.qs.order_by("index", "pk")
        except Exception:
            pass
        return _instances_via_through_table(model, cot_field, content_type, obj_id)

    try:
        return model.objects.filter(
            **{f"{cot_field.name}__pk": obj_id}
        ).order_by("index", "pk")
    except Exception:
        return _instances_via_through_table(model, cot_field, content_type, obj_id)


def _scan_field_instances(model, cot_field, content_type: ContentType, obj_id: int):
    """Legacy name: resolve references via indexed through-table lookup."""
    try:
        return _instances_via_through_table(model, cot_field, content_type, obj_id)
    except Exception:
        pass

    match_pks = []
    for instance in model.objects.all().order_by("index", "pk"):
        related = getattr(instance, cot_field.name, None)
        if related is None or not hasattr(related, "all"):
            continue
        for obj in related.all():
            if (
                ContentType.objects.get_for_model(obj).pk == content_type.pk
                and obj.pk == obj_id
            ):
                match_pks.append(instance.pk)
                break
    return model.objects.filter(pk__in=match_pks).order_by("index", "pk")


def scan_cot_security_references(
    content_type: ContentType,
    obj_id: int,
) -> list[dict]:
    """
    Flat list of matches sorted for panel display.

    Each entry: rulebook, field, field_name, rule, sort_key tuple.
    """
    matches: list[dict] = []
    for cot in iter_deployed_cot_rulebooks():
        try:
            model = cot.get_model()
        except Exception:
            continue
        rulebook = _panel_rulebook(cot)
        from extras.choices import CustomFieldTypeChoices

        mobj_fields = list(
            cot.fields.filter(type=CustomFieldTypeChoices.TYPE_MULTIOBJECT).order_by(
                "weight", "name"
            )
        )
        for cot_field in mobj_fields:
            if not _field_allows_content_type(cot_field, content_type):
                continue
            for instance in _instances_for_field(
                model, cot_field, content_type, obj_id
            ):
                rule = _PanelRule(
                    instance=instance,
                    cot_slug=cot.slug,
                    name=_rule_display_name(instance),
                )
                matches.append(
                    {
                        "rulebook": rulebook,
                        "field": _panel_field(cot_field),
                        "field_name": cot_field.name,
                        "field_weight": cot_field.weight,
                        "rule": rule,
                        "rulebook_name": rulebook.name,
                        "rulebook_slug": cot.slug,
                    }
                )
    matches.sort(
        key=lambda row: (
            row["rulebook_name"].lower(),
            row["field_weight"],
            row["field"].name.lower(),
            getattr(row["rule"]._instance, "index", 0) or 0,
            row["rule"].pk,
        )
    )
    return matches


def iter_cot_security_rulebook_matches(
    content_type: ContentType,
    obj_id: int,
    *,
    offset: int = 0,
    limit: int | None = None,
) -> Iterator[dict]:
    """Yield deduplicated matches (rulebook, field, rule) with offset/limit."""
    seen: set[tuple] = set()
    skipped = 0
    yielded = 0
    for row in scan_cot_security_references(content_type, obj_id):
        key = (row["rulebook"].pk, row["field"].pk, row["rule"].pk)
        if key in seen:
            continue
        seen.add(key)
        if skipped < offset:
            skipped += 1
            continue
        if limit is not None and yielded >= limit:
            break
        yielded += 1
        yield row


def _attach_panel_urls(matches: list[dict], *, panel_url) -> None:
    for row in matches:
        rulebook = row["rulebook"]
        rule = row["rule"]
        rule.nsm_panel_filter_url = panel_url(
            build_cot_rule_name_column_filter_url(rulebook.slug, rule.name)
        )


def _resolve_cot_field(rulebook_pk: int, field_pk: int):
    """Return ``(cot, cot_field, model)`` for panel/API field lookups."""
    from extras.choices import CustomFieldTypeChoices

    for cot in iter_deployed_cot_rulebooks():
        if cot.pk != rulebook_pk:
            continue
        try:
            model = cot.get_model()
        except Exception:
            return None, None, None
        cot_field = (
            cot.fields.filter(
                pk=field_pk,
                type=CustomFieldTypeChoices.TYPE_MULTIOBJECT,
            )
            .first()
        )
        if cot_field is None:
            return cot, None, model
        return cot, cot_field, model
    return None, None, None


def fetch_cot_security_field_rules(
    content_type: ContentType,
    obj_id: int,
    *,
    rulebook_pk: int,
    field_pk: int,
    offset: int = 0,
    limit: int = API_BATCH_DEFAULT,
) -> tuple[list[dict], int]:
    """
    Return ``(rows, total)`` for one rulebook field.

    Each row matches ``scan_cot_security_references`` shape for API serialization.
    """
    cot, cot_field, model = _resolve_cot_field(rulebook_pk, field_pk)
    if cot is None or cot_field is None or model is None:
        return [], 0
    if not _field_allows_content_type(cot_field, content_type):
        return [], 0

    qs = _instances_for_field(model, cot_field, content_type, obj_id)
    total = qs.count()
    if total == 0:
        return [], 0

    rulebook = _panel_rulebook(cot)
    field = _panel_field(cot_field)
    rows: list[dict] = []
    for instance in qs[offset : offset + limit]:
        rows.append(
            {
                "rulebook": rulebook,
                "field": field,
                "field_name": cot_field.name,
                "field_weight": cot_field.weight,
                "rule": _PanelRule(
                    instance=instance,
                    cot_slug=cot.slug,
                    name=_rule_display_name(instance),
                ),
                "rulebook_name": rulebook.name,
                "rulebook_slug": cot.slug,
            }
        )
    return rows, total


def build_cot_security_rulebook_groups(
    content_type: ContentType,
    obj_id: int,
    *,
    panel_url,
    first_page: int = FIRST_PAGE_DEFAULT,
) -> dict:
    """
    Build ``nsm_rulebook_groups`` structure for ``security_links.html``.

    Rule links are not included in the initial payload; field groups expose
    counts only and are filled via ``fetch_cot_security_field_rules`` on expand.

    Returns dict with keys: rulebook_groups, unique_rules_total, total_items.
    """
    del first_page  # kept for call-site compatibility

    by_rulebook: dict[int, dict] = {}
    rb_order: list[int] = []
    total_items = 0
    unique_rules_total = 0

    cot_models: dict[int, object] = {}
    rb_field_counts: dict[int, list[tuple[object, int]]] = {}

    for cot, cot_field in _iter_matching_security_fields(content_type):
        try:
            model = cot_models.get(cot.pk)
            if model is None:
                model = cot.get_model()
                cot_models[cot.pk] = model
        except Exception:
            continue

        rulebook = _panel_rulebook(cot)
        rb_pk = rulebook.pk
        count = _count_field_references(model, cot_field, content_type, obj_id)
        if count == 0:
            continue

        f_pk = cot_field.pk
        total_items += count
        rb_field_counts.setdefault(rb_pk, []).append((cot_field, count))

        if rb_pk not in by_rulebook:
            by_rulebook[rb_pk] = {
                "rulebook": rulebook,
                "_fields": {},
                "_field_order": [],
            }
            rb_order.append(rb_pk)

        rb_data = by_rulebook[rb_pk]
        if f_pk not in rb_data["_fields"]:
            rb_data["_fields"][f_pk] = {
                "field": _panel_field(cot_field),
                "rule_count": count,
            }
            rb_data["_field_order"].append(f_pk)

    rulebook_groups = []
    for rb_pk in rb_order:
        data = by_rulebook[rb_pk]
        rb = data["rulebook"]
        model = cot_models.get(rb_pk)
        fields_with_counts = rb_field_counts.get(rb_pk, [])
        if model is None:
            unique_count = sum(count for _, count in fields_with_counts)
        else:
            unique_count = _rulebook_unique_reference_count(
                model,
                content_type,
                obj_id,
                fields_with_counts,
            )
        unique_rules_total += unique_count
        field_groups = [
            {
                "field": data["_fields"][f_pk]["field"],
                "rule_count": data["_fields"][f_pk]["rule_count"],
            }
            for f_pk in data["_field_order"]
        ]
        rulebook_groups.append(
            {
                "rulebook": rb,
                "field_groups": field_groups,
                "unique_count": unique_count,
                "rules_tab_url": panel_url(rb.get_rules_tab_url()),
            }
        )

    return {
        "rulebook_groups": rulebook_groups,
        "unique_rules_total": unique_rules_total,
        "total_items": total_items,
    }
