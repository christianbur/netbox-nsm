"""Shorter labels for polymorphic custom-object form sub-fields when NSM is installed."""

from __future__ import annotations

import functools

__all__ = (
    "patch_poly_subfield_labels",
    "poly_subfield_short_label",
    "poly_subfield_type_label",
    "shorten_rulebook_poly_subfield_labels",
)


def poly_subfield_short_label(field_label: str) -> str:
    """Return the type suffix from a compound polymorphic sub-field label.

    NSM labels look like ``Zones (Source) (Zone)``; forms show only ``Zone``.
    """
    label = (field_label or "").strip()
    if label.endswith(")"):
        return label.rsplit("(", 1)[-1].rstrip(")").strip()
    return label


def shorten_rulebook_poly_subfield_labels(form) -> None:
    """Use type-only labels on polymorphic sub-fields; section headers carry context."""
    poly_m2m_groups = getattr(form, "custom_object_type_poly_m2m_groups", {})
    for sub_names, _field_label in poly_m2m_groups.values():
        for sub_name in sub_names:
            field = form.fields.get(sub_name)
            if field is None:
                continue
            short = poly_subfield_short_label(field.label)
            if short:
                field.label = short

    for ct_sub, (obj_sub, _field_label) in getattr(
        form, "custom_object_type_poly_obj_pairs", {}
    ).items():
        for sub_name in (ct_sub, obj_sub):
            field = form.fields.get(sub_name)
            if field is None:
                continue
            short = poly_subfield_short_label(field.label)
            if short:
                field.label = short


@functools.lru_cache(maxsize=256)
def poly_subfield_type_label(content_type_id: int) -> str:
    """Return a short type suffix for polymorphic sub-field labels.

    Prefers the TypeConfig model label (singular COT ``verbose_name``) over
    NetBox's default ``App > Model`` breadcrumb from ``object_type_name()``.
    """
    from django.contrib.contenttypes.models import ContentType

    from netbox_nsm.models import TypeConfig
    from utilities.object_types import object_type_name

    tc = (
        TypeConfig.objects.filter(content_type_id=content_type_id)
        .select_related("content_type")
        .first()
    )
    if tc is not None:
        label = (tc.content_type_label or "").strip()
        if label:
            return label

    ct = ContentType.objects.get(pk=content_type_id)
    return object_type_name(ct, include_app=False)


def patch_poly_subfield_labels() -> None:
    """Monkey-patch netbox-custom-objects polymorphic sub-field label rendering."""
    try:
        import netbox_custom_objects.views as co_views
        from extras.choices import CustomFieldTypeChoices
        from netbox_custom_objects.constants import APP_LABEL
        from utilities.forms.fields import (
            DynamicModelChoiceField,
            DynamicModelMultipleChoiceField,
        )
    except ImportError:
        return

    def _build_poly_subfields(field, set_initial: bool = False):
        is_multi = field.type == CustomFieldTypeChoices.TYPE_MULTIOBJECT
        field_class = (
            DynamicModelMultipleChoiceField if is_multi else DynamicModelChoiceField
        )
        field_label = field.label or field.name.replace("_", " ").title()
        group_name = (field.group_name or "").strip()
        if group_name:
            from netbox_nsm.rulebooks.rulebook_groups import (
                resolve_group_name_for_display,
            )

            group_label = resolve_group_name_for_display(group_name)
            if group_label and group_label != field_label:
                field_label = f"{field_label} ({group_label})"

        for ot in field.related_object_types.all():
            sub_model = ot.model_class()
            if sub_model is None:
                continue
            sub_name = co_views._poly_sub_name(field.name, ot.app_label, ot.model)
            sub_field = field_class(
                queryset=sub_model.objects.all(),
                required=False,
                label=f"{field_label} ({poly_subfield_type_label(ot.pk)})",
                selector=ot.app_label != APP_LABEL,
            )
            if set_initial:
                sub_field.initial = None
            yield sub_name, sub_field

    co_views._build_poly_subfields = _build_poly_subfields
