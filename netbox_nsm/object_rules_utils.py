"""Helpers for object detail → security rulebook filter links."""

from __future__ import annotations

from urllib.parse import quote

from django.urls import reverse

from netbox_nsm.display_utils import get_display_template_map, render_object_display
from netbox_nsm.policy_grid_payload import conditions_to_filter_query
from netbox_nsm.query.parser import Condition


def build_object_field_rules_filter_url(
    rulebook,
    field,
    obj,
    content_type,
    *,
    display_template_map=None,
) -> str:
    """
    Rules tab URL filtering *rulebook* to rows where *obj* appears in *field*.

    Example: Destination.Zones.name == "trust"
    """
    if not rulebook or not field or obj is None or content_type is None:
        return ""

    tmpl_map = (
        display_template_map
        if display_template_map is not None
        else get_display_template_map()
    )
    obj_name = render_object_display(obj, content_type.pk, tmpl_map)

    type_segment = None
    type_configs = getattr(field, "type_configs", None)
    if type_configs is not None:
        for ft in type_configs.all():
            tc = ft.type_config
            if tc.content_type_id == content_type.pk:
                type_segment = tc.name
                break
    else:
        from netbox_nsm.models import RulebookFieldType

        for ft in RulebookFieldType.objects.filter(field=field).select_related(
            "type_config__content_type"
        ):
            if ft.type_config.content_type_id == content_type.pk:
                type_segment = ft.type_config.name
                break

    if type_segment:
        cond = Condition(
            field=field.name,
            type_segment=type_segment,
            sub_field="name",
            operator="=",
            value=obj_name,
        )
    else:
        cond = Condition(
            field=field.name,
            sub_field="Name",
            operator="=",
            value=obj_name,
        )

    base = reverse("plugins:netbox_nsm:rulebook_rules", args=[rulebook.pk])
    q = conditions_to_filter_query([cond])
    return f"{base}?filter_q={quote(q, safe='')}"
