from django.utils.translation import gettext_lazy as _
from django.conf import settings
from netbox.plugins import PluginMenuButton, PluginMenuItem, PluginMenu

plugin_settings = settings.PLUGINS_CONFIG.get("netbox_nsm", {})

address_menu_items = (
    PluginMenuItem(
        link="plugins:netbox_nsm:addressset_list",
        link_text=_("Address Sets"),
        permissions=["netbox_nsm.view_addressset"],
        buttons=(
            PluginMenuButton(
                "plugins:netbox_nsm:addressset_add",
                _("Add"),
                "mdi mdi-plus-thick",
                permissions=["netbox_nsm.add_addressset"],
            ),
            PluginMenuButton(
                "plugins:netbox_nsm:addressset_bulk_import",
                _("Import"),
                "mdi mdi-upload",
                permissions=["netbox_nsm.add_addressset"],
            ),
        ),
    ),
    PluginMenuItem(
        link="plugins:netbox_nsm:address_list",
        link_text=_("Addresses"),
        permissions=["netbox_nsm.view_address"],
        buttons=(
            PluginMenuButton(
                "plugins:netbox_nsm:address_add",
                _("Add"),
                "mdi mdi-plus-thick",
                permissions=["netbox_nsm.add_address"],
            ),
            PluginMenuButton(
                "plugins:netbox_nsm:address_bulk_import",
                _("Import"),
                "mdi mdi-upload",
                permissions=["netbox_nsm.add_address"],
            ),
        ),
    ),
    PluginMenuItem(
        link="plugins:netbox_nsm:customprefix_list",
        link_text=_("Custom Prefixes"),
        permissions=["netbox_nsm.view_customprefix"],
        buttons=(
            PluginMenuButton(
                "plugins:netbox_nsm:customprefix_add",
                _("Add"),
                "mdi mdi-plus-thick",
                permissions=["netbox_nsm.add_customprefix"],
            ),
            PluginMenuButton(
                "plugins:netbox_nsm:customprefix_bulk_import",
                _("Import"),
                "mdi mdi-upload",
                permissions=["netbox_nsm.add_customprefix"],
            ),
        ),
    ),
)
application_menu_items = (
    PluginMenuItem(
        link="plugins:netbox_nsm:applicationitem_list",
        link_text=_("Application Items"),
        permissions=["netbox_nsm.view_applicationitem"],
        buttons=(
            PluginMenuButton(
                "plugins:netbox_nsm:applicationitem_add",
                _("Add"),
                "mdi mdi-plus-thick",
                permissions=["netbox_nsm.add_applicationitem"],
            ),
            PluginMenuButton(
                "plugins:netbox_nsm:applicationitem_bulk_import",
                _("Import"),
                "mdi mdi-upload",
                permissions=["netbox_nsm.add_applicationitem"],
            ),
        ),
    ),
    PluginMenuItem(
        link="plugins:netbox_nsm:application_list",
        link_text=_("Applications"),
        permissions=["netbox_nsm.view_application"],
        buttons=(
            PluginMenuButton(
                "plugins:netbox_nsm:application_add",
                _("Add"),
                "mdi mdi-plus-thick",
                permissions=["netbox_nsm.add_application"],
            ),
            PluginMenuButton(
                "plugins:netbox_nsm:application_bulk_import",
                _("Import"),
                "mdi mdi-upload",
                permissions=["netbox_nsm.add_application"],
            ),
        ),
    ),
    PluginMenuItem(
        link="plugins:netbox_nsm:applicationset_list",
        link_text=_("Application Sets"),
        permissions=["netbox_nsm.view_applicationset"],
        buttons=(
            PluginMenuButton(
                "plugins:netbox_nsm:applicationset_add",
                _("Add"),
                "mdi mdi-plus-thick",
                permissions=["netbox_nsm.add_applicationset"],
            ),
            PluginMenuButton(
                "plugins:netbox_nsm:applicationset_bulk_import",
                _("Import"),
                "mdi mdi-upload",
                permissions=["netbox_nsm.add_applicationset"],
            ),
        ),
    ),
)
security_menu_items = (
    PluginMenuItem(
        link="plugins:netbox_nsm:securityzonematrix_list",
        link_text=_("Security Zones Matrix"),
        permissions=["netbox_nsm.view_securityzonematrix"],
        buttons=(
            PluginMenuButton(
                "plugins:netbox_nsm:securityzonematrix_add",
                _("Add"),
                "mdi mdi-plus-thick",
                permissions=["netbox_nsm.add_securityzonematrix"],
            ),
            PluginMenuButton(
                "plugins:netbox_nsm:securityzonematrix_bulk_import",
                _("Import"),
                "mdi mdi-upload",
                permissions=["netbox_nsm.add_securityzonematrix"],
            ),
        ),
    ),
    PluginMenuItem(
        link="plugins:netbox_nsm:securityzonematrixpolicy_list",
        link_text=_("Security Zones Matrix Policies"),
        permissions=["netbox_nsm.view_securityzonematrixpolicy"],
        buttons=(
            PluginMenuButton(
                "plugins:netbox_nsm:securityzonematrixpolicy_add",
                _("Add"),
                "mdi mdi-plus-thick",
                permissions=["netbox_nsm.add_securityzonematrixpolicy"],
            ),
            PluginMenuButton(
                "plugins:netbox_nsm:securityzonematrixpolicy_bulk_import",
                _("Import"),
                "mdi mdi-upload",
                permissions=["netbox_nsm.add_securityzonematrixpolicy"],
            ),
        ),
    ),
    PluginMenuItem(
        link="plugins:netbox_nsm:securityzonepolicy_list",
        link_text=_("Security Zone Policies"),
        permissions=["netbox_nsm.view_securityzonepolicy"],
        buttons=(
            PluginMenuButton(
                "plugins:netbox_nsm:securityzonepolicy_add",
                _("Add"),
                "mdi mdi-plus-thick",
                permissions=["netbox_nsm.add_securityzonepolicy"],
            ),
            PluginMenuButton(
                "plugins:netbox_nsm:securityzonepolicy_bulk_import",
                _("Import"),
                "mdi mdi-upload",
                permissions=["netbox_nsm.add_securityzonepolicy"],
            ),
        ),
    ),
)

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

builder_menu_items = ()

objects_menu_items = (
    PluginMenuItem(
        link="plugins:netbox_nsm:object_tabs_root",
        link_text=_("Objekts"),
        permissions=["netbox_nsm.view_address", "netbox_nsm.view_objectaction"],
    ),
)


if plugin_settings.get("top_level_menu"):
    # Build groups tuple conditionally
    groups = (
        (_("Builder"), builder_menu_items),
        (_("Objekts"), objects_menu_items),
        # (_("Address Book"), address_menu_items),
        (_("Security Zones"), security_menu_items),
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
        # + address_menu_items
        + security_menu_items
        + security_policy_menu_items
    )
    if plugin_settings.get("assignments_menu"):
        menu_items = menu_items + assignments_menu_items
