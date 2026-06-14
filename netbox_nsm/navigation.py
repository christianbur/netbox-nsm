from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify

from netbox.plugins import (
    PluginMenu,
    PluginMenuButton,
    PluginMenuItem,
    get_plugin_config,
)
from netbox.navigation.menu import MenuGroup

from netbox_nsm.core.plugin_labels import get_nsm_menu_label
from netbox_nsm.core.setup_flags import setup_menu_enabled
from netbox_nsm.navigation_objects import build_nsm_objects_menu_group

_TYPE_CONFIG_MENU_ITEM = PluginMenuItem(
    link="plugins:netbox_nsm:objectconfig_list",
    link_text=_("Object Config"),
    permissions=["netbox_nsm.view_typeconfig"],
)

_SETUP_MENU_ITEM = PluginMenuItem(
    link="plugins:netbox_nsm:setup",
    link_text=_("Setup"),
    permissions=["netbox_nsm.view_typeconfig"],
)


def _build_configuration_menu():
    config_items = []
    try:
        if setup_menu_enabled():
            config_items.append(_SETUP_MENU_ITEM)
    except Exception:
        pass
    config_items.append(_TYPE_CONFIG_MENU_ITEM)
    return ((_("Configuration"), tuple(config_items)),)


class DynamicPluginMenu(PluginMenu):
    def __init__(self, label, groups_builder, icon_class="mdi mdi-puzzle"):
        self._label_resolver = label if callable(label) else lambda: label
        self._groups_builder = groups_builder
        self.icon_class = icon_class

    @property
    def label(self):
        return self._label_resolver()

    @property
    def groups(self):
        return [
            MenuGroup(label=label, items=items)
            for label, items in self._groups_builder()
        ]

    @property
    def name(self):
        return slugify(str(self.label))


nsm_rulebook_menu_items = (
    PluginMenuItem(
        link="plugins:netbox_nsm:rulebook_list",
        link_text=_("Rulebooks"),
        auth_required=True,
        permissions=[],
        buttons=(
            PluginMenuButton(
                "plugins:netbox_nsm:cot_rulebook_add",
                _("Add"),
                "mdi mdi-plus-thick",
                permissions=[],
            ),
        ),
    ),
)


def _analysis_menu_items():
    return (
        PluginMenuItem(
            link="plugins:netbox_nsm:object_analyzer",
            link_text=_("Object Analyzer"),
            auth_required=True,
            permissions=[],
        ),
    )


def build_menu_groups():
    """Build sidebar groups for the top-level NSM menu."""
    groups = list(_build_configuration_menu())
    objects_group = build_nsm_objects_menu_group()
    if objects_group is not None:
        groups.append(objects_group)
    groups.extend(
        (
            ((_("Rulebooks"), nsm_rulebook_menu_items),)
            + ((_("Analysis"), _analysis_menu_items()),)
        )
    )
    return groups


if get_plugin_config("netbox_nsm", "top_level_menu", True):

    menu = DynamicPluginMenu(
        label=get_nsm_menu_label,
        groups_builder=build_menu_groups,
        icon_class="mdi mdi-security",
    )
else:
    menu_items = nsm_rulebook_menu_items
