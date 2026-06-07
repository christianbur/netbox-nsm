"""Copy a rulebook schema (metadata + field layout) into a new rulebook."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from utilities.querydict import prepare_cloned_fields

from dcim.models import Device
from virtualization.models import VirtualMachine

from netbox_nsm.models import Rulebook, RulebookField, RulebookFieldType
from netbox_nsm.rulebook_field_utils import load_rulebook_fields_for_detail

__all__ = (
    "COPY_SCHEMA_PARAM",
    "copy_rulebook_fields_layout",
    "populate_rulebook_form_from_source",
    "rulebook_schema_copy_add_url",
)

COPY_SCHEMA_PARAM = "copy_schema_from"

_RULEBOOK_FIELD_ATTRS = (
    "name",
    "sort_order",
    "placement",
    "field_kind",
    "visible",
    "searchable",
    "filterable",
    "facet_mode",
    "facet_weight",
    "max_visible_pills",
    "show_colored_pills",
)

_RULEBOOK_FIELD_TYPE_ATTRS = (
    "sort_order",
    "max_items",
    "name_filter_regex",
    "visible",
    "facet_mode",
)


def rulebook_schema_copy_add_url(source: Rulebook, *, return_url: str | None = None) -> str:
    """Build the rulebook add URL with cloned metadata and schema source pk."""
    params = prepare_cloned_fields(source)
    params[COPY_SCHEMA_PARAM] = str(source.pk)
    if return_url:
        params["return_url"] = return_url
    base = reverse("plugins:netbox_nsm:rulebook_add")
    encoded = params.urlencode()
    return f"{base}?{encoded}" if encoded else base


def _assignment_pks(rulebook: Rulebook, model):
    ct = ContentType.objects.get_for_model(model)
    return list(
        rulebook.assignments.filter(assigned_object_type=ct).values_list(
            "assigned_object_id", flat=True
        )
    )


def populate_rulebook_form_from_source(form, source: Rulebook) -> None:
    """Pre-fill assignment fields on a new rulebook form from *source*."""
    form.initial["assigned_devices"] = _assignment_pks(source, Device)
    form.initial["assigned_vms"] = _assignment_pks(source, VirtualMachine)


def copy_rulebook_fields_layout(source: Rulebook, target: Rulebook) -> None:
    """Replicate rulebook columns and type configs from *source* onto *target*."""
    target_fields = {
        field.slug: field for field in load_rulebook_fields_for_detail(target)
    }

    for src_field in load_rulebook_fields_for_detail(source):
        tgt_field = target_fields.get(src_field.slug)
        if tgt_field is None:
            tgt_field = RulebookField.objects.create(
                rulebook=target,
                slug=src_field.slug,
            )
            target_fields[src_field.slug] = tgt_field

        for attr in _RULEBOOK_FIELD_ATTRS:
            setattr(tgt_field, attr, getattr(src_field, attr))
        tgt_field.save()

        if src_field.is_system_field:
            continue

        tgt_field.type_configs.all().delete()
        for src_type in src_field.field_type_list:
            RulebookFieldType.objects.create(
                field=tgt_field,
                type_config=src_type.type_config,
                **{
                    attr: getattr(src_type, attr)
                    for attr in _RULEBOOK_FIELD_TYPE_ATTRS
                },
            )


COPY_SCHEMA_LABEL = _("Copy schema")
