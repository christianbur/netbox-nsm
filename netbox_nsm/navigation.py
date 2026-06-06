from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from django.conf import settings
from netbox.plugins import PluginMenuButton, PluginMenuItem, PluginMenu
from netbox.navigation.menu import MenuGroup

from netbox_nsm.plugin_labels import get_nsm_menu_label

plugin_settings = settings.PLUGINS_CONFIG.get("netbox_nsm", {})


objects_menu_items = ()


def _build_object_groups():
    try:
        groups = []
        config_items = []
        if plugin_settings.get("setup_menu", True):
            config_items.append(
                PluginMenuItem(
                    link="plugins:netbox_nsm:setup",
                    link_text=_("Setup"),
                    permissions=["netbox_nsm.view_typeconfig"],
                )
            )
        config_items.append(
            PluginMenuItem(
                link="plugins:netbox_nsm:typeconfig_list",
                link_text=_("Type Config"),
                permissions=["netbox_nsm.view_typeconfig"],
            )
        )
        groups.append((_("Configuration"), tuple(config_items)))
        return tuple(groups)
    except Exception:
        return ((_("Objects"), objects_menu_items),)


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
        return slugify(self.label)


nsm_rulebook_menu_items = (
    PluginMenuItem(
        link="plugins:netbox_nsm:rulebook_list",
        link_text=_("Rulebooks"),
        permissions=["netbox_nsm.view_rulebook"],
        buttons=(
            PluginMenuButton(
                "plugins:netbox_nsm:rulebook_add",
                _("Add"),
                "mdi mdi-plus-thick",
                permissions=["netbox_nsm.add_rulebook"],
            ),
        ),
    ),
)

assignments_menu_items = (
    PluginMenuItem(
        link="plugins:netbox_nsm:rulebookassignment_list",
        link_text=_("Rulebook Assignments"),
        permissions=["netbox_nsm.view_rulebookassignment"],
    ),
)


def _resolve_ip_analysis_rulebook():
    """Rulebook for Security → Analysis → IP Analysis (menu needs a concrete pk)."""
    from netbox_nsm.models import Rulebook, RulebookTypeChoices

    pk = plugin_settings.get("ip_analysis_rulebook_id")
    if pk is not None:
        rulebook = Rulebook.objects.filter(pk=pk).first()
        if rulebook:
            return rulebook

    for name in (
        plugin_settings.get("ip_analysis_rulebook_name"),
        "Enterprise - TrustSec Infra",
    ):
        if not name:
            continue
        rulebook = Rulebook.objects.filter(name=name).first()
        if rulebook:
            return rulebook

    return (
        Rulebook.objects.filter(rulebook_type=RulebookTypeChoices.SECURITY_RULES)
        .order_by("name", "pk")
        .first()
    )


def _ip_analysis_menu_item():
    from django.urls import reverse

    rulebook = _resolve_ip_analysis_rulebook()
    if rulebook is None:
        return None
    item = PluginMenuItem(
        link="plugins:netbox_nsm:rulebook_list",
        link_text=_("IP Analysis"),
        permissions=["netbox_nsm.view_rulebook"],
    )
    item.url = reverse(
        "plugins:netbox_nsm:rulebook_ipanalysis",
        kwargs={"pk": rulebook.pk},
    )
    return item


def _analysis_menu_items():
    items = []
    ip_item = _ip_analysis_menu_item()
    if ip_item is not None:
        items.append(ip_item)
    items.append(
        PluginMenuItem(
            link="plugins:netbox_nsm:object_analyzer",
            link_text=_("Object Analyzer"),
            permissions=["netbox_nsm.view_rulebook"],
        )
    )
    return tuple(items)


if plugin_settings.get("top_level_menu"):

    def _menu_groups():
        groups = (
            _build_object_groups()
            + ((_("Rulebooks"), nsm_rulebook_menu_items),)
            + ((_("Analysis"), _analysis_menu_items()),)
        )
        if plugin_settings.get("assignments_menu"):
            groups = groups + ((_("Assignments"), assignments_menu_items),)
        return groups

    menu = DynamicPluginMenu(
        label=get_nsm_menu_label,
        groups_builder=_menu_groups,
        icon_class="mdi mdi-security",
    )
else:
    menu_items = nsm_rulebook_menu_items
    if plugin_settings.get("assignments_menu"):
        menu_items = menu_items + assignments_menu_items
