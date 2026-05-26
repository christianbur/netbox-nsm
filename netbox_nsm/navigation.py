from django.utils.translation import gettext_lazy as _
from django.conf import settings
from netbox.plugins import PluginMenuButton, PluginMenuItem, PluginMenu

plugin_settings = settings.PLUGINS_CONFIG.get("netbox_nsm", {})

address_menu_items = ()

builder_menu_items = ()

security_policy_menu_items = (
    PluginMenuItem(
        link="plugins:netbox_nsm:securityzonepolicyrulebook_list",
        link_text=_("Security Policy"),
        permissions=["netbox_nsm.view_securityzonepolicyrulebook"],
        buttons=(
            PluginMenuButton(
                "plugins:netbox_nsm:securityzonepolicyrulebook_add",
                _("Add"),
                "mdi mdi-plus-thick",
                permissions=["netbox_nsm.add_securityzonepolicyrulebook"],
            ),
        ),
    ),
)

assignments_menu_items = (
    PluginMenuItem(
        link="plugins:netbox_nsm:securityzonepolicyrulebookassignment_list",
        link_text=_("Security Rulebook Assignments"),
        permissions=["netbox_nsm.view_securityzonepolicyrulebookassignment"],
    ),
)

objects_menu_items = (
    PluginMenuItem(
        link="plugins:netbox_nsm:object_tabs_root",
        link_text=_("Objekts"),
        permissions=["netbox_nsm.view_objectaction"],
    ),
)


if plugin_settings.get("top_level_menu"):
    # Build groups tuple conditionally
    groups = (
        (_("Builder"), builder_menu_items),
        (_("Objekts"), objects_menu_items),
        (_("Security Policy"), security_policy_menu_items),
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
        builder_menu_items
        + objects_menu_items
        + security_policy_menu_items
    )
    if plugin_settings.get("assignments_menu"):
        menu_items = menu_items + assignments_menu_items

