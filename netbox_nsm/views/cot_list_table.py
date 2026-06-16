"""List-table helpers for polymorphic GFK columns on Custom Object types."""

from __future__ import annotations

__all__ = (
    "CotPolymorphicListTableMixin",
    "_non_sortable_polymorphic_object_fields",
    "_request_without_sort_on_blocked_fields",
    "_strip_blocked_ordering",
    "apply_cot_polymorphic_list_table_patch",
)


def _non_sortable_polymorphic_object_fields(cot) -> frozenset[str]:
    """Polymorphic GFK columns cannot be used in SQL ``ORDER BY``."""
    if cot is None:
        return frozenset()
    from extras.choices import CustomFieldTypeChoices

    return frozenset(
        cot.fields.filter(
            type=CustomFieldTypeChoices.TYPE_OBJECT,
            is_polymorphic=True,
        ).values_list("name", flat=True)
    )


def _strip_blocked_ordering(ordering, blocked: frozenset[str]):
    if not ordering or not blocked:
        return ordering
    cleaned = tuple(o for o in ordering if o.lstrip("-") not in blocked)
    return cleaned


def _request_without_sort_on_blocked_fields(request, blocked: frozenset[str]):
    sort = request.GET.get("sort", "")
    if not sort or sort.lstrip("-") not in blocked:
        return request
    params = request.GET.copy()
    params.pop("sort", None)
    request.GET = params
    return request


class CotPolymorphicListTableMixin:
    """Strip invalid ordering on polymorphic object (GFK) list columns."""

    def _prepare_list_table_request(self, request):
        """Drop invalid sort params before django-tables2 configures ordering."""
        cot = getattr(self, "custom_object_type", None)
        blocked = _non_sortable_polymorphic_object_fields(cot)
        if not blocked:
            return request

        request = _request_without_sort_on_blocked_fields(request, blocked)

        if request.user.is_authenticated and cot is not None:
            model = cot.get_model()
            table_name = f"{model._meta.object_name}Table"
            config_key = f"tables.{table_name}.ordering"
            ordering = request.user.config.get(config_key)
            cleaned = _strip_blocked_ordering(ordering, blocked)
            if cleaned != ordering:
                request.user.config.set(config_key, list(cleaned), commit=True)
        return request

    def _finalize_polymorphic_list_table(self, table):
        blocked = _non_sortable_polymorphic_object_fields(
            getattr(self, "custom_object_type", None)
        )
        for name in blocked:
            if name in table.base_columns:
                table.base_columns[name].orderable = False
        if table.order_by:
            table.order_by = _strip_blocked_ordering(table.order_by, blocked)
        return table

    def get_table(self, data, request, bulk_actions=True):
        request = self._prepare_list_table_request(request)
        table = super().get_table(data, request, bulk_actions=bulk_actions)
        return self._finalize_polymorphic_list_table(table)


def apply_cot_polymorphic_list_table_patch() -> None:
    """Patch ``CustomObjectListView`` (``/plugins/custom-objects/…`` routes)."""
    try:
        from netbox_custom_objects.views import CustomObjectListView
    except ImportError:
        return

    if getattr(CustomObjectListView.get_table, "_nsm_polymorphic_sort_patch", False):
        return

    _original_get_table = CustomObjectListView.get_table

    def get_table(self, data, request, bulk_actions=True):
        request = CotPolymorphicListTableMixin._prepare_list_table_request(self, request)
        table = _original_get_table(self, data, request, bulk_actions=bulk_actions)
        return CotPolymorphicListTableMixin._finalize_polymorphic_list_table(self, table)

    get_table._nsm_polymorphic_sort_patch = True
    CustomObjectListView.get_table = get_table
