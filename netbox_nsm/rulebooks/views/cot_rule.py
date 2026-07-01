"""Custom-object rule form hooks: index/zone prefill and shorter poly sub-field labels."""

from __future__ import annotations

from extras.choices import CustomFieldTypeChoices

from netbox_nsm.core.poly_subfield_labels import shorten_rulebook_poly_subfield_labels
from netbox_nsm.rulebooks.matrix.cot_matrix_tab_context import resolve_matrix_field_names
from netbox_nsm.rulebooks.cot_rule_clone import apply_rule_clone_prefill
from netbox_nsm.rulebooks.cot_rule_index import next_rulebook_index
from netbox_nsm.rulebooks.templates import is_deployed_rulebook_slug

__all__ = (
    "apply_matrix_zone_prefill",
    "patch_cot_rule_add_form",
    "poly_m2m_subfield_name",
    "resolve_zone_field_initial",
    "shorten_rulebook_poly_subfield_labels",
)


def poly_m2m_subfield_name(field_name: str, app_label: str, model: str) -> str:
    """Form sub-field name for one content type of a polymorphic M2M field."""
    return f"{field_name}__{app_label}__{model}"


def resolve_zone_field_initial(cot, field_name: str, zone_pk) -> tuple[str, list[int]] | None:
    """Map a zone PK to the correct form field name and initial PK list."""
    try:
        pk = int(zone_pk)
    except (TypeError, ValueError):
        return None

    try:
        field = cot.fields.prefetch_related("related_object_types").get(name=field_name)
    except Exception:
        return None

    if field.type != CustomFieldTypeChoices.TYPE_MULTIOBJECT:
        return None

    if field.is_polymorphic:
        for object_type in field.related_object_types.all():
            model = object_type.model_class()
            if model is None:
                continue
            if model.objects.filter(pk=pk).exists():
                sub_name = poly_m2m_subfield_name(
                    field_name,
                    object_type.app_label,
                    object_type.model,
                )
                return sub_name, [pk]
        return None

    if not field.related_object_type_id:
        return None
    related_model = field.related_object_type.model_class()
    if related_model is None or not related_model.objects.filter(pk=pk).exists():
        return None
    return field_name, [pk]


def apply_matrix_zone_prefill(cot, initial: dict) -> None:
    """Translate matrix ``source_zone`` / ``destination_zone`` query params into form initial."""
    matrix_fields = resolve_matrix_field_names(cot)
    if matrix_fields is None:
        return
    src_field, dst_field = matrix_fields
    for param, field_name in (
        ("source_zone", src_field),
        ("destination_zone", dst_field),
    ):
        zone_pk = initial.pop(param, None)
        if zone_pk is None:
            continue
        resolved = resolve_zone_field_initial(cot, field_name, zone_pk)
        if resolved is None:
            continue
        sub_name, pks = resolved
        if sub_name not in initial:
            initial[sub_name] = pks


def _is_rulebook_cot_form(view) -> bool:
    obj = getattr(view, "object", None)
    if obj is None:
        return False
    cot = getattr(obj, "custom_object_type", None)
    return cot is not None and is_deployed_rulebook_slug(cot.slug)


def _should_prefill_rule_index(view) -> bool:
    obj = getattr(view, "object", None)
    return _is_rulebook_cot_form(view) and obj is not None and not obj.pk


def patch_cot_rule_add_form() -> None:
    """Monkey-patch CustomObjectEditView.get_form for nsm_rb_* rule add/edit forms."""
    try:
        from netbox_custom_objects.views import CustomObjectEditView
    except ImportError:
        return

    if getattr(CustomObjectEditView, "_nsm_rule_index_patch", False):
        return

    original_get_form = CustomObjectEditView.get_form

    def get_form(self, model):
        form_class = original_get_form(self, model)
        if not _is_rulebook_cot_form(self):
            return form_class

        original_init = form_class.__init__
        cot = self.object.custom_object_type
        prefill_index = _should_prefill_rule_index(self)

        def init_with_rulebook_defaults(form_self, *args, **kwargs):
            if prefill_index:
                if "initial" not in kwargs:
                    kwargs["initial"] = {}
                apply_rule_clone_prefill(cot, kwargs["initial"])
                if "index" not in kwargs["initial"]:
                    kwargs["initial"]["index"] = next_rulebook_index(cot)
                apply_matrix_zone_prefill(cot, kwargs["initial"])
            original_init(form_self, *args, **kwargs)
            shorten_rulebook_poly_subfield_labels(form_self)

        form_class.__init__ = init_with_rulebook_defaults
        return form_class

    CustomObjectEditView.get_form = get_form
    CustomObjectEditView._nsm_rule_index_patch = True
