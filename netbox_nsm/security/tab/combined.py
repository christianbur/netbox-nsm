"""Bidirectional custom-object reference rows for the Security tab."""

from __future__ import annotations

import logging
from collections import defaultdict

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from extras.choices import CustomFieldTypeChoices
from netbox.context import current_request
from netbox_custom_objects.models import CustomObjectTypeField

try:
    from netbox_custom_objects.utilities import restrict_to_viewable
except ImportError:
    def restrict_to_viewable(user, objects):
        """Fallback when older netbox-custom-objects lacks restrict_to_viewable."""
        visible = []
        for obj in objects:
            try:
                qs = type(obj).objects.filter(pk=obj.pk)
                if hasattr(qs, "restrict"):
                    qs = qs.restrict(user, "view")
                if qs.exists():
                    visible.append(obj)
            except Exception:
                continue
        return visible

from netbox_nsm.security.links.cot_link_schema import object_fields_for_cot
from netbox_nsm.security.tab.cot_metadata import cot_link_table_flag

logger = logging.getLogger("netbox_nsm.tabs")

_CUSTOM_OBJECTS_APP = "netbox_custom_objects"

# Sentinel menu filter removed — Security tab uses unfiltered linked-object rows.
__all__ = (
    "_JunctionField",
    "_OutgoingFieldProxy",
    "_count_linked_custom_objects",
    "_cot_is_junction",
    "_get_field_value",
    "_get_linked_custom_objects",
    "_outgoing_rows",
    "_transform_junctions",
    "is_untransformed_junction_row",
    "reference_q",
)


def _cot_is_junction(cot) -> bool:
    """True when *cot* is flagged as an n:m link / junction table."""
    return cot_link_table_flag(cot)


def is_untransformed_junction_row(row_obj, field) -> bool:
    """True when the row is still the junction object, not a rewritten far endpoint."""
    if getattr(field, "is_junction_row", False):
        return False
    cot = getattr(field, "custom_object_type", None)
    if not _cot_is_junction(cot):
        return False
    row_cot = getattr(row_obj, "custom_object_type", None)
    if row_cot is None:
        return False
    if getattr(row_cot, "pk", None) == getattr(cot, "pk", None):
        return True
    return getattr(row_cot, "slug", None) == getattr(cot, "slug", None)


def reference_q(
    host_ct_id,
    host_pk,
    field_name,
    field_type,
    is_polymorphic,
    through_model_name=None,
):
    """Build a Q selecting CO rows whose *field_name* references the host object."""
    if field_type == CustomFieldTypeChoices.TYPE_OBJECT:
        if is_polymorphic:
            return Q(
                **{
                    f"{field_name}_content_type_id": host_ct_id,
                    f"{field_name}_object_id": host_pk,
                }
            )
        return Q(**{f"{field_name}_id": host_pk})

    if field_type == CustomFieldTypeChoices.TYPE_MULTIOBJECT:
        if is_polymorphic:
            try:
                through = apps.get_model(_CUSTOM_OBJECTS_APP, through_model_name)
            except LookupError:
                logger.exception(
                    "Could not resolve through model %r for polymorphic field %s",
                    through_model_name,
                    field_name,
                )
                return Q()
            return Q(
                pk__in=through.objects.filter(
                    content_type_id=host_ct_id, object_id=host_pk
                ).values("source_id")
            )
        return Q(**{field_name: host_pk})

    return Q()


def _restrict_or_warn(qs, user, *, label):
    try:
        return qs.restrict(user, "view")
    except AttributeError:
        logger.warning(
            "%s lacks restrict(user, view); per-row permission filter skipped", label
        )
        return qs


def _cot_is_type_metadata_reference(cot) -> bool:
    """True when *cot* may produce Security tab CO reference rows."""
    if cot is None:
        return False
    if cot_link_table_flag(cot):
        return True
    try:
        from netbox_nsm.type_metadata.config import resolve_nsm_config_for_cot

        return resolve_nsm_config_for_cot(cot) is not None
    except Exception:
        return False


def _iter_linked_fields(instance):
    """Yield (field, model, q) for every CO field referencing *instance*."""
    content_type = ContentType.objects.get_for_model(instance._meta.model)
    type_choices = [
        CustomFieldTypeChoices.TYPE_OBJECT,
        CustomFieldTypeChoices.TYPE_MULTIOBJECT,
    ]

    if not CustomObjectTypeField.objects.filter(
        Q(related_object_type=content_type, is_polymorphic=False)
        | Q(related_object_types=content_type, is_polymorphic=True),
        type__in=type_choices,
    ).exists():
        return

    non_poly = CustomObjectTypeField.objects.filter(
        related_object_type=content_type,
        is_polymorphic=False,
        type__in=type_choices,
    ).select_related("custom_object_type")

    poly = CustomObjectTypeField.objects.filter(
        related_object_types=content_type,
        is_polymorphic=True,
        type__in=type_choices,
    ).select_related("custom_object_type")

    model_cache = {}
    for field in list(non_poly) + list(poly):
        if not _cot_is_type_metadata_reference(field.custom_object_type):
            continue
        cot_id = field.custom_object_type_id
        model = model_cache.get(cot_id)
        if model is None:
            try:
                model = field.custom_object_type.get_model()
            except Exception:
                logger.exception("Could not get model for CustomObjectType %s", cot_id)
                continue
            model_cache[cot_id] = model
        q = reference_q(
            content_type.id,
            instance.pk,
            field.name,
            field.type,
            field.is_polymorphic,
            field.through_model_name,
        )
        if not q.children:
            continue
        yield field, model, q


_LINKED_FIELDS_REQUEST_CACHE = "_nsm_security_linked_fields"


def _linked_fields(instance):
    request = current_request.get()
    if request is None:
        return list(_iter_linked_fields(instance))
    cache = getattr(request, _LINKED_FIELDS_REQUEST_CACHE, None)
    if cache is None:
        cache = {}
        setattr(request, _LINKED_FIELDS_REQUEST_CACHE, cache)
    key = (instance._meta.label, instance.pk)
    if key not in cache:
        cache[key] = list(_iter_linked_fields(instance))
    return cache[key]


def _object_fields_for_cot(cot):
    return object_fields_for_cot(cot)


def _field_has_value(instance, field):
    value = getattr(instance, field.name, None)
    if field.type == CustomFieldTypeChoices.TYPE_OBJECT:
        return value is not None
    try:
        return value is not None and value.exists()
    except Exception:
        return False


def _type_label(endpoint):
    cot = getattr(endpoint, "custom_object_type", None)
    if cot is not None:
        return str(cot)
    try:
        return endpoint._meta.verbose_name.title()
    except Exception:
        return type(endpoint).__name__


class _OutgoingFieldProxy:
    """Thin wrapper that only overrides ``__str__`` for outgoing rows."""

    is_junction_row = False
    type_label = None

    def __init__(self, field, label):
        object.__setattr__(self, "_field", field)
        object.__setattr__(self, "_label", label)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_field"), name)

    def __str__(self):
        return object.__getattribute__(self, "_label")


class _JunctionField:
    """Synthetic field for a junction-resolved Security tab row."""

    is_junction_row = True
    type = "_junction"
    is_polymorphic = False
    name = "_junction"

    def __init__(self, junction_cot, type_label, via_obj, label):
        self.custom_object_type = junction_cot
        self.type_label = type_label
        self.via_obj = via_obj
        self._label = label

    def __str__(self):
        return self._label


def _far_field(near_field):
    """The other object field on a link-table COT (two object fields topology)."""
    cot = getattr(near_field, "custom_object_type", None)
    if cot is None:
        return None
    others = [f for f in _object_fields_for_cot(cot) if f.name != near_field.name]
    return others[0] if len(others) == 1 else None


def _transform_junctions(rows):
    out = []
    for obj, field in rows:
        try:
            cot = getattr(field, "custom_object_type", None)
            if _cot_is_junction(cot):
                far = _far_field(field)
                endpoint = getattr(obj, far.name, None) if far is not None else None
                if endpoint is not None and hasattr(endpoint, "get_absolute_url"):
                    jf = _JunctionField(
                        cot,
                        _type_label(endpoint),
                        obj,
                        _("linked via %(cot)s") % {"cot": cot},
                    )
                    out.append((endpoint, jf))
                    continue
        except Exception:
            logger.exception("junction traversal failed for a row; leaving it untouched")
        out.append((obj, field))
    return out


def _outgoing_far_type_label(instance, field):
    value = getattr(instance, field.name, None)
    if value is None:
        return None
    if field.type == CustomFieldTypeChoices.TYPE_OBJECT:
        return _type_label(value)
    try:
        first = value.all().first()
    except Exception:
        return None
    return _type_label(first) if first is not None else None


def _outgoing_rows(instance):
    cot = getattr(instance, "custom_object_type", None)
    if cot is None:
        return []
    if not _cot_is_type_metadata_reference(cot):
        return []
    is_junction = _cot_is_junction(cot)
    rows = []
    try:
        for field in _object_fields_for_cot(cot):
            if _field_has_value(instance, field):
                label = _("%(field)s (this object \u2192 value)") % {"field": field}
                proxy = _OutgoingFieldProxy(field, label)
                if is_junction:
                    proxy.type_label = _outgoing_far_type_label(instance, field)
                rows.append((instance, proxy))
    except Exception:
        logger.exception("could not build outgoing reference rows for %s", instance)
    return rows


def _get_linked_custom_objects(instance, user=None):
    from django.db.models import prefetch_related_objects

    results = []
    for field, model, q in _linked_fields(instance):
        qs = model.objects.filter(q).prefetch_related("tags")
        if field.type == CustomFieldTypeChoices.TYPE_OBJECT and not field.is_polymorphic:
            qs = qs.select_related(field.name)
        if user is not None:
            qs = _restrict_or_warn(qs, user, label=model._meta.label)
        for obj in qs:
            results.append((obj, field))

    results = _transform_junctions(results)
    results.extend(_outgoing_rows(instance))
    return results


def _count_linked_custom_objects(instance):
    request = current_request.get()
    user = getattr(request, "user", None) if request is not None else None
    total = len(_get_linked_custom_objects(instance, user=user))
    return total if total > 0 else None


def _get_field_value(obj, field, user=None):
    if getattr(field, "is_junction_row", False):
        return getattr(field, "via_obj", None)
    if isinstance(field, _OutgoingFieldProxy):
        real = object.__getattribute__(field, "_field")
        return _get_field_value(obj, real, user=user)
    if field.type == CustomFieldTypeChoices.TYPE_OBJECT:
        return getattr(obj, field.name, None)
    if field.type == CustomFieldTypeChoices.TYPE_MULTIOBJECT:
        manager = getattr(obj, field.name, None)
        if manager is None:
            return []
        qs = manager.all()
        if user is not None:
            try:
                qs = qs.restrict(user, "view")
            except AttributeError:
                return restrict_to_viewable(user, list(qs))
            return list(qs)
        return list(qs)
    return None
