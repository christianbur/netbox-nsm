"""Clone an existing COT rulebook rule into the add form."""

from __future__ import annotations

from django.apps import apps as django_apps
from django.utils.translation import gettext_lazy as _

from extras.choices import CustomFieldTypeChoices

from netbox_nsm.rulebooks.cot_rule_index import next_rulebook_index


def _poly_m2m_subfield_name(field_name: str, app_label: str, model: str) -> str:
    return f"{field_name}__{app_label}__{model}"

__all__ = (
    "build_rule_clone_initial",
    "build_rule_clone_url",
    "cloned_rule_name",
)


def cloned_rule_name(source_name: str) -> str:
    """Default display name for a cloned rule."""
    text = str(source_name or "").strip()
    if not text:
        return ""
    return _("Copy of %(name)s") % {"name": text}


def build_rule_clone_url(request, cot_slug: str, pk, *, return_path: str) -> str:
    """Add-form URL that pre-fills a new rule from ``copy_from``."""
    from urllib.parse import urlencode

    from django.urls import reverse

    from netbox_nsm.core.branch_urls import with_branch_query
    from netbox_nsm.security.actions.panel_link_actions import append_return_url

    base = reverse(
        "plugins:netbox_custom_objects:customobject_add",
        kwargs={"custom_object_type": cot_slug},
    )
    url = f"{base}?{urlencode({'copy_from': pk})}"
    return append_return_url(with_branch_query(url, request), return_path)


def build_rule_clone_initial(cot, source) -> dict:
    """Build form ``initial`` values from an existing rule (except index/name)."""
    from netbox_custom_objects.constants import APP_LABEL

    initial: dict = {}
    scalar_types = {
        CustomFieldTypeChoices.TYPE_TEXT,
        CustomFieldTypeChoices.TYPE_LONGTEXT,
        CustomFieldTypeChoices.TYPE_INTEGER,
        CustomFieldTypeChoices.TYPE_DECIMAL,
        CustomFieldTypeChoices.TYPE_BOOLEAN,
        CustomFieldTypeChoices.TYPE_DATE,
        CustomFieldTypeChoices.TYPE_DATETIME,
        CustomFieldTypeChoices.TYPE_URL,
        CustomFieldTypeChoices.TYPE_JSON,
        CustomFieldTypeChoices.TYPE_SELECT,
    }

    for field in cot.fields.prefetch_related("related_object_types").order_by(
        "group_name", "weight", "name"
    ):
        if field.name in ("index", "name"):
            continue

        if field.type in scalar_types:
            if hasattr(source, field.name):
                initial[field.name] = getattr(source, field.name)
            continue

        if field.type == CustomFieldTypeChoices.TYPE_MULTIOBJECT:
            if field.is_polymorphic:
                try:
                    from netbox_nsm.core.cot_m2m_through import (
                        field_uses_polymorphic_through,
                        get_field_through_model,
                        read_m2m_ref_pairs,
                    )

                    through = get_field_through_model(field)
                    if through is None:
                        raise LookupError(field.through_model_name)
                    if not field_uses_polymorphic_through(field):
                        related = getattr(source, field.name, None)
                        if related is not None and hasattr(related, "values_list"):
                            initial[field.name] = list(
                                related.values_list("pk", flat=True)
                            )
                        continue
                    rows = read_m2m_ref_pairs(through, source.pk)
                    by_ct: dict[int, list] = {}
                    for ct_id, obj_id in rows:
                        by_ct.setdefault(ct_id, []).append(obj_id)
                    for object_type in field.related_object_types.all():
                        model = object_type.model_class()
                        if model is None:
                            continue
                        sub_name = _poly_m2m_subfield_name(
                            field.name,
                            object_type.app_label,
                            object_type.model,
                        )
                        initial[sub_name] = by_ct.get(object_type.pk, [])
                except (LookupError, AttributeError, ValueError):
                    pass
            else:
                related = getattr(source, field.name, None)
                if related is not None and hasattr(related, "values_list"):
                    initial[field.name] = list(
                        related.values_list("pk", flat=True)
                    )
            continue

        if field.type == CustomFieldTypeChoices.TYPE_OBJECT and field.is_polymorphic:
            ct_field = f"{field.name}_content_type"
            obj_field = f"{field.name}_object_id"
            ct_value = getattr(source, ct_field, None)
            obj_value = getattr(source, obj_field, None)
            if ct_value and obj_value:
                initial[f"{field.name}__ct"] = ct_value.pk
                initial[f"{field.name}__obj"] = obj_value
            continue

        if field.type == CustomFieldTypeChoices.TYPE_OBJECT:
            related = getattr(source, field.name, None)
            if related is not None and getattr(related, "pk", None):
                initial[field.name] = related.pk

    initial["index"] = next_rulebook_index(cot)
    initial["name"] = cloned_rule_name(getattr(source, "name", ""))
    return initial


def apply_rule_clone_prefill(cot, initial: dict) -> None:
    """Merge ``copy_from`` query param into add-form initial data."""
    copy_from = initial.pop("copy_from", None)
    if not copy_from:
        return
    try:
        source_pk = int(copy_from)
    except (TypeError, ValueError):
        return
    model = cot.get_model()
    source = model.objects.filter(pk=source_pk).first()
    if source is None:
        return
    clone_initial = build_rule_clone_initial(cot, source)
    for key, value in clone_initial.items():
        initial.setdefault(key, value)
