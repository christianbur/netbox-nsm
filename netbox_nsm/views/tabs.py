from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.db.models import Count, F, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce

from ipam.models import IPAddress, IPRange, Prefix
from dcim.models import Device, VirtualDeviceContext
from virtualization.models import VirtualMachine
from netbox_nsm.models import (
    Address,
    NatPoolMember,
    NatRule,
    SecurityZone,
)
from netbox_nsm.utilities import get_address_set_hierarchy

from netbox.views import generic
from utilities.views import register_model_view, ViewTab


def _count_subquery(qs):
    return Coalesce(
        Subquery(
            qs.order_by()
            .annotate(_group=Value(1))
            .values("_group")
            .annotate(c=Count("pk", distinct=True))
            .values("c")[:1]
        ),
        Value(0),
        output_field=IntegerField(),
    )


def _annotate_ipam_security_queryset(
    queryset,
    *,
    assigned_object_model,
    nat_pool_member_field,
    nat_rule_source_field,
    nat_rule_destination_field,
):
    nat_pool_member_filter = {f"{nat_pool_member_field}_id": OuterRef("pk")}
    nat_rule_source_filter = {nat_rule_source_field: OuterRef("pk")}
    nat_rule_destination_filter = {nat_rule_destination_field: OuterRef("pk")}

    return queryset.annotate(
        nat_pool_member_count=_count_subquery(
            NatPoolMember.objects.filter(**nat_pool_member_filter)
        ),
        nat_rule_count=_count_subquery(
            NatRule.objects.filter(
                Q(**nat_rule_source_filter) | Q(**nat_rule_destination_filter)
            )
        ),
        address_count=_count_subquery(
            Address.objects.filter(
                assigned_object_type__app_label="ipam",
                assigned_object_type__model=assigned_object_model,
                assigned_object_id=OuterRef("pk"),
            )
        ),
        security_zone_count=_count_subquery(
            SecurityZone.objects.filter(
                addresses__address__assigned_object_type__app_label="ipam",
                addresses__address__assigned_object_type__model=assigned_object_model,
                addresses__address__assigned_object_id=OuterRef("pk"),
            ).distinct()
        ),
    ).annotate(
        related_total_count=(
            F("nat_pool_member_count")
            + F("nat_rule_count")
            + F("address_count")
            + F("security_zone_count")
        )
    )


def _annotate_ipaddress_queryset(queryset):
    return _annotate_ipam_security_queryset(
        queryset,
        assigned_object_model="ipaddress",
        nat_pool_member_field="address",
        nat_rule_source_field="source_addresses",
        nat_rule_destination_field="destination_addresses",
    )


def _annotate_prefix_queryset(queryset):
    return _annotate_ipam_security_queryset(
        queryset,
        assigned_object_model="prefix",
        nat_pool_member_field="prefix",
        nat_rule_source_field="source_prefixes",
        nat_rule_destination_field="destination_prefixes",
    )


def _annotate_iprange_queryset(queryset):
    return _annotate_ipam_security_queryset(
        queryset,
        assigned_object_model="iprange",
        nat_pool_member_field="address_range",
        nat_rule_source_field="source_ranges",
        nat_rule_destination_field="destination_ranges",
    )


def _related_total_count(obj, model, annotate_queryset):
    # Tabs are rendered from the base IPAddress object view; ensure the badge works even if the instance isn't annotated.
    if hasattr(obj, "related_total_count"):
        return obj.related_total_count
    return (
        annotate_queryset(model.objects.filter(pk=obj.pk))
        .values_list("related_total_count", flat=True)
        .first()
        or 0
    )


def _ipaddress_related_total_count(obj):
    return max(
        _related_total_count(obj, IPAddress, _annotate_ipaddress_queryset),
        _policy_context_related_total_count("ipam", "ipaddress", obj.pk),
    )


def _prefix_related_total_count(obj):
    return max(
        _related_total_count(obj, Prefix, _annotate_prefix_queryset),
        _policy_context_related_total_count("ipam", "prefix", obj.pk),
    )


def _iprange_related_total_count(obj):
    return max(
        _related_total_count(obj, IPRange, _annotate_iprange_queryset),
        _policy_context_related_total_count("ipam", "iprange", obj.pk),
    )


def _policy_context(app_label, model, object_id):
    return get_address_set_hierarchy(
        app_label=app_label,
        model=model,
        object_id=object_id,
    )


def _policy_context_related_total_count(app_label, model, object_id):
    policy_context = _policy_context(app_label, model, object_id)
    return (
        len(policy_context.get("address_ids", ()))
        + len(policy_context.get("inherited_address_ids", ()))
        + len(policy_context.get("address_set_hierarchy_rows", ()))
        + len(policy_context.get("policy_paths", ()))
    )


# Registry of all security object types shown in the Security tab.
# To add a new type, append one entry here — no template changes needed.
NSM_OBJECT_TYPES = []


def _nsm_security_tab_context(instance, user=None):
    """Build the generic nsm_tabs context for any object's security template.

    Uses the generic GFK filters (assigned_object_type + assigned_object_id) so
    that any NetBox model, including third-party plugin models, works without
    needing a model-specific filterset method.
    """
    ct = ContentType.objects.get_for_model(instance)
    pk = instance.pk
    return_url = instance.get_absolute_url()

    tabs = []
    for t in NSM_OBJECT_TYPES:
        count = t["count_model"].objects.filter(
            assigned_object_type=ct, assigned_object_id=pk
        ).count()
        list_url = (
            reverse(t["list_url_name"])
            + f"?embedded=True&assigned_object_type={ct.app_label}.{ct.model}&assigned_object_id={pk}&return_url={return_url}"
        )
        add_url = (
            reverse(t["add_url_name"])
            + f"?assigned_object_type={ct.pk}&assigned_object_id={pk}&return_url={return_url}"
        )
        can_assign = user.has_perm(f"netbox_nsm.{t['perm']}") if user else True
        tabs.append(
            {
                "tab_id": t["tab_id"],
                "tab_label": t["tab_label"],
                "assign_label": t["assign_label"],
                "count": count,
                "list_url": list_url,
                "add_url": add_url,
                "can_assign": can_assign,
            }
        )

    first_tab = next((t["tab_id"] for t in tabs if t["count"] > 0), None)
    return {
        "nsm_tabs": tabs,
        "first_nsm_tab": first_tab,
    }


@register_model_view(Device, name="security")
class DeviceSecurityView(generic.ObjectView):
    queryset = Device.objects.all()
    template_name = "netbox_nsm/device/security.html"
    tab = ViewTab(
        label=_("Security"),
    )

    def get_extra_context(self, request, instance):
        return _nsm_security_tab_context(instance, user=request.user)


@register_model_view(VirtualDeviceContext, name="security")
class VirtualDeviceContextSecurityView(generic.ObjectView):
    queryset = VirtualDeviceContext.objects.all()
    template_name = "netbox_nsm/virtual_device_context/security.html"
    tab = ViewTab(
        label=_("Security"),
    )

    def get_extra_context(self, request, instance):
        return _nsm_security_tab_context(instance, user=request.user)


@register_model_view(VirtualMachine, name="security")
class VirtualMachineSecurityView(generic.ObjectView):
    queryset = VirtualMachine.objects.all()
    template_name = "netbox_nsm/virtualmachine/security.html"
    tab = ViewTab(
        label=_("Security"),
    )

    def get_extra_context(self, request, instance):
        return _nsm_security_tab_context(instance, user=request.user)


@register_model_view(IPAddress, name="security")
class IPAddressSecurityView(generic.ObjectView):
    queryset = _annotate_ipaddress_queryset(IPAddress.objects.all())
    template_name = "netbox_nsm/ipaddress/security.html"
    tab = ViewTab(
        label=_("Security"),
        badge=_ipaddress_related_total_count,
        hide_if_empty=True,
    )

    def get_extra_context(self, request, instance):
        return {
            "policy_context": _policy_context("ipam", "ipaddress", instance.pk),
        }


@register_model_view(Prefix, name="security")
class PrefixSecurityView(generic.ObjectView):
    queryset = _annotate_prefix_queryset(Prefix.objects.all())
    template_name = "netbox_nsm/prefix/security.html"
    tab = ViewTab(
        label=_("Security"),
        badge=_prefix_related_total_count,
        hide_if_empty=True,
    )

    def get_extra_context(self, request, instance):
        return {
            "policy_context": _policy_context("ipam", "prefix", instance.pk),
        }


@register_model_view(IPRange, name="security")
class IPRangeSecurityView(generic.ObjectView):
    queryset = _annotate_iprange_queryset(IPRange.objects.all())
    template_name = "netbox_nsm/iprange/security.html"
    tab = ViewTab(
        label=_("Security"),
        badge=_iprange_related_total_count,
        hide_if_empty=True,
    )

    def get_extra_context(self, request, instance):
        return {
            "policy_context": _policy_context("ipam", "iprange", instance.pk),
        }
