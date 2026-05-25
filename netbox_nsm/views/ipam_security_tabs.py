"""
NSM Security (Groups) tabs for ipam.IPAddress and ipam.Prefix.

Adds a "NSM Groups" tab to the NetBox IP address and prefix detail views,
showing every ObjectGroup chain that references the object — including
inherited matches via containing prefixes for IP addresses.
"""

from ipam.models import IPAddress, Prefix
from netbox.views import generic
from utilities.views import ViewTab, register_model_view
from django.utils.translation import gettext_lazy as _

__all__ = (
    "IPAddressNsmGroupsView",
    "PrefixNsmGroupsView",
)


def _compute_chains(app_label, model_name, pk):
    from netbox_nsm.utilities import get_group_chains_for_object
    return get_group_chains_for_object(app_label, model_name, pk)


def _ip_badge(instance):
    chains = _compute_chains("ipam", "ipaddress", instance.pk)
    return len(chains) or None


def _prefix_badge(instance):
    chains = _compute_chains("ipam", "prefix", instance.pk)
    return len(chains) or None


@register_model_view(
    IPAddress,
    name="nsm_groups",
    path="nsm-groups",
)
class IPAddressNsmGroupsView(generic.ObjectView):
    queryset = IPAddress.objects.all()
    template_name = "netbox_nsm/ipaddress/security.html"

    tab = ViewTab(
        label=_("Security"),
        permission="netbox_nsm.view_objectgroup",
        badge=_ip_badge,
        hide_if_empty=False,
        weight=600,
    )

    def get_extra_context(self, request, instance):
        chains = _compute_chains("ipam", "ipaddress", instance.pk)
        return {
            "group_chains": chains,
            "policy_context": {},
        }


@register_model_view(
    Prefix,
    name="nsm_groups",
    path="nsm-groups",
)
class PrefixNsmGroupsView(generic.ObjectView):
    queryset = Prefix.objects.all()
    template_name = "netbox_nsm/prefix/security.html"

    tab = ViewTab(
        label=_("Security"),
        permission="netbox_nsm.view_objectgroup",
        badge=_prefix_badge,
        hide_if_empty=False,
        weight=600,
    )

    def get_extra_context(self, request, instance):
        chains = _compute_chains("ipam", "prefix", instance.pk)
        return {
            "group_chains": chains,
            "policy_context": {},
        }
