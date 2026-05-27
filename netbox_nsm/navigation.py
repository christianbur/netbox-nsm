from django.utils.translation import gettext_lazy as _
from django.conf import settings
from netbox.plugins import PluginMenuButton, PluginMenuItem, PluginMenu

plugin_settings = settings.PLUGINS_CONFIG.get("netbox_nsm", {})

objects_menu_items = (
    PluginMenuItem(
        link="plugins:netbox_nsm:object_tabs_root",
        link_text=_("Objects"),
        permissions=["netbox_nsm.view_securityobject"],
    ),
    PluginMenuItem(
        link="plugins:netbox_nsm:object_builder_root",
        link_text=_("Object-Builder"),
        permissions=["netbox_nsm.view_securityobjecttype"],
    ),
)

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
    groups = (
        (_("Objects"), objects_menu_items),
        (_("Security Policies"), security_policy_menu_items),
    )
    if plugin_settings.get("assignments_menu"):
        groups = groups + ((_("Assignments"), assignments_menu_items),)

    menu = PluginMenu(
        label=_("Security"),
        groups=groups,
        icon_class="mdi mdi-security",
    )
else:
    menu_items = (
        objects_menu_items
        + security_policy_menu_items
    )
    if plugin_settings.get("assignments_menu"):
        menu_items = menu_items + assignments_menu_items

