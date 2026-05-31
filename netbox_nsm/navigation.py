from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from django.conf import settings
from netbox.plugins import PluginMenuButton, PluginMenuItem, PluginMenu
from netbox.navigation.menu import MenuGroup
from urllib.parse import quote

plugin_settings = settings.PLUGINS_CONFIG.get("netbox_nsm", {})


def _make_literal_menu_item(url, link_text, permissions):
    item = PluginMenuItem(
        link="plugins:netbox_nsm:setup",
        link_text=link_text,
        permissions=permissions,
    )
    item.url = url
    return item


objects_menu_items = ()


def _build_object_groups():
    try:
        groups = []
        groups.append(
            (
                _("Configuration"),
                (
                    PluginMenuItem(
                        link="plugins:netbox_nsm:setup",
                        link_text=_("Setup"),
                        permissions=["netbox_nsm.view_typeconfig"],
                    ),
                    PluginMenuItem(
                        link="plugins:netbox_nsm:object_builder_root",
                        link_text=_("Object Builder"),
                        permissions=["netbox_nsm.view_typeconfig"],
                    ),
                    PluginMenuItem(
                        link="plugins:netbox_nsm:typeconfig_list",
                        link_text=_("Type Config"),
                        permissions=["netbox_nsm.view_typeconfig"],
                    ),
                ),
            )
        )
        return tuple(groups)
    except Exception:
        return ((_("Objects"), objects_menu_items),)


class DynamicPluginMenu(PluginMenu):
    def __init__(self, label, groups_builder, icon_class="mdi mdi-puzzle"):
        self.label = label
        self._groups_builder = groups_builder
        self.icon_class = icon_class

    @property
    def groups(self):
        return [
            MenuGroup(label=label, items=items)
            for label, items in self._groups_builder()
        ]

    @property
    def name(self):
        return slugify(self.label)

security_policy_menu_items = (
    PluginMenuItem(
        link="plugins:netbox_nsm:securitypolicyrulebook_list",
        link_text=_("Security Policies"),
        permissions=["netbox_nsm.view_securitypolicyrulebook"],
        buttons=(
            PluginMenuButton(
                "plugins:netbox_nsm:securitypolicyrulebook_add",
                _("Add"),
                "mdi mdi-plus-thick",
                permissions=["netbox_nsm.add_securitypolicyrulebook"],
            ),
        ),
    ),
)

assignments_menu_items = (
    PluginMenuItem(
        link="plugins:netbox_nsm:securitypolicyassignment_list",
        link_text=_("Security Rulebook Assignments"),
        permissions=["netbox_nsm.view_securitypolicyassignment"],
    ),
)


if plugin_settings.get("top_level_menu"):
    def _menu_groups():
        analysis_items = (
            _make_literal_menu_item(
                "/plugins/netbox-nsm/security-policy/4/ipanalysis/",
                _("IP Analysis"),
                ["netbox_nsm.view_securitypolicyrulebook"],
            ),
            PluginMenuItem(
                link="plugins:netbox_nsm:object_analyzer",
                link_text=_("Demo - Object Analyzer"),
                permissions=["netbox_nsm.view_securitypolicyrulebook"],
            ),
        )
        groups = (
            _build_object_groups()
            + ((_("Security Policies"), security_policy_menu_items),)
            + ((_("Analysis"), analysis_items),)
        )
        if plugin_settings.get("assignments_menu"):
            groups = groups + ((_("Assignments"), assignments_menu_items),)
        return groups

    menu = DynamicPluginMenu(
        label=_("Security"),
        groups_builder=_menu_groups,
        icon_class="mdi mdi-security",
    )
else:
    menu_items = security_policy_menu_items
    if plugin_settings.get("assignments_menu"):
        menu_items = menu_items + assignments_menu_items
