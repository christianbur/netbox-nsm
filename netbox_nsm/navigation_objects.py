"""NSM Custom Object list entries for the Security sidebar."""

from __future__ import annotations

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from netbox.plugins import PluginMenuButton, PluginMenuItem

from netbox_nsm.objects.cot_routes import (
    iter_nsm_objects_menu_cots,
    nsm_object_menu_label_for_cot,
)
from netbox_nsm.objects.type_config_specs import default_sort_order_for_slug

__all__ = (
    "build_nsm_objects_menu_group",
    "iter_nsm_object_menu_items",
)


def _sorted_nsm_objects_menu_cots():
    return sorted(
        iter_nsm_objects_menu_cots(),
        key=lambda cot: (
            default_sort_order_for_slug(cot.slug),
            nsm_object_menu_label_for_cot(cot).casefold(),
            cot.slug,
        ),
    )


def iter_nsm_object_menu_items():
    """Yield list menu items for COTs with metadata menu bucket ``objects``."""
    for cot in _sorted_nsm_objects_menu_cots():
        model = cot.get_model()
        add_button = PluginMenuButton(
            None,
            _("Add"),
            "mdi mdi-plus-thick",
        )
        add_button.url = reverse_lazy(
            "plugins:netbox_nsm:nsm_object_add",
            kwargs={"custom_object_type": cot.slug},
        )
        bulk_import_button = PluginMenuButton(
            None,
            _("Import"),
            "mdi mdi-upload",
        )
        bulk_import_button.url = reverse_lazy(
            "plugins:netbox_nsm:nsm_object_bulk_import",
            kwargs={"custom_object_type": cot.slug},
        )
        menu_item = PluginMenuItem(
            link=None,
            link_text=_(nsm_object_menu_label_for_cot(cot)),
            buttons=(add_button, bulk_import_button),
            auth_required=True,
            permissions=[f"netbox_custom_objects.view_{model._meta.model_name}"],
        )
        menu_item.url = reverse_lazy(
            "plugins:netbox_nsm:nsm_object_list",
            kwargs={"custom_object_type": cot.slug},
        )
        yield menu_item


def build_nsm_objects_menu_group():
    """Return a single ``Objects`` menu group, or ``None`` when empty."""
    items = tuple(iter_nsm_object_menu_items())
    if not items:
        return None
    return (_("Objects"), items)
