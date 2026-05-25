from typing import List

import strawberry
import strawberry_django

from .types import (
    NetBoxSecurityCustomPrefixType,
    NetBoxSecurityAddressType,
    NetBoxSecurityAddressSetType,
    NetBoxSecurityAddressListType,
    NetBoxSecurityApplicationItemType,
    NetBoxSecurityApplicationType,
    NetBoxSecurityApplicationSetType,
    NetBoxSecuritySecurityZoneType,
    NetBoxSecuritySecurityZonePolicyType,
    NetBoxSecurityNatPoolType,
    NetBoxSecurityNatPoolMemberType,
    NetBoxSecurityNatRuleSetType,
    NetBoxSecurityNatRuleType,
    NetBoxSecurityPolicerType,
    NetBoxSecurityFirewallFilterType,
    NetBoxSecurityFirewallFilterRuleType,
)


@strawberry.type(name="Query")
class NetBoxSecurityCustomPrefixQuery:
    netbox_nsm_customprefix: NetBoxSecurityCustomPrefixType = (
        strawberry_django.field()
    )
    netbox_nsm_customprefix_list: List[NetBoxSecurityCustomPrefixType] = (
        strawberry_django.field()
    )


@strawberry.type(name="Query")
class NetBoxSecurityAddressQuery:
    netbox_nsm_address: NetBoxSecurityAddressType = strawberry_django.field()
    netbox_nsm_address_list: List[NetBoxSecurityAddressType] = (
        strawberry_django.field()
    )


@strawberry.type(name="Query")
class NetBoxSecurityAddressSetQuery:
    netbox_nsm_addressset: NetBoxSecurityAddressSetType = strawberry_django.field()
    netbox_nsm_addressset_list: List[NetBoxSecurityAddressSetType] = (
        strawberry_django.field()
    )


@strawberry.type(name="Query")
class NetBoxSecurityAddressListQuery:
    netbox_nsm_addresslist: NetBoxSecurityAddressListType = (
        strawberry_django.field()
    )
    netbox_nsm_addresslist_list: List[NetBoxSecurityAddressListType] = (
        strawberry_django.field()
    )


@strawberry.type(name="Query")
class NetBoxSecurityApplicationItemQuery:
    netbox_nsm_applicationitem: NetBoxSecurityApplicationItemType = (
        strawberry_django.field()
    )
    netbox_nsm_applicationitem_list: List[NetBoxSecurityApplicationItemType] = (
        strawberry_django.field()
    )


@strawberry.type(name="Query")
class NetBoxSecurityApplicationQuery:
    netbox_nsm_application: NetBoxSecurityApplicationType = (
        strawberry_django.field()
    )
    netbox_nsm_application_list: List[NetBoxSecurityApplicationType] = (
        strawberry_django.field()
    )


@strawberry.type(name="Query")
class NetBoxSecurityApplicationSetQuery:
    netbox_nsm_applicationset: NetBoxSecurityApplicationSetType = (
        strawberry_django.field()
    )
    netbox_nsm_applicationset_list: List[NetBoxSecurityApplicationSetType] = (
        strawberry_django.field()
    )


@strawberry.type(name="Query")
class NetBoxSecuritySecurityZoneQuery:
    netbox_nsm_securityzone: NetBoxSecuritySecurityZoneType = (
        strawberry_django.field()
    )
    netbox_nsm_securityzone_list: List[NetBoxSecuritySecurityZoneType] = (
        strawberry_django.field()
    )


@strawberry.type(name="Query")
class NetBoxSecuritySecurityZonePolicyQuery:
    netbox_nsm_securityzonepolicy: NetBoxSecuritySecurityZonePolicyType = (
        strawberry_django.field()
    )
    netbox_nsm_securityzonepolicy_list: List[
        NetBoxSecuritySecurityZonePolicyType
    ] = strawberry_django.field()


@strawberry.type(name="Query")
class NetBoxSecurityNatPoolQuery:
    netbox_nsm_natpool: NetBoxSecurityNatPoolType = strawberry_django.field()
    netbox_nsm_natpool_list: List[NetBoxSecurityNatPoolType] = (
        strawberry_django.field()
    )


@strawberry.type(name="Query")
class NetBoxSecurityNatPoolMemberQuery:
    netbox_nsm_natpoolmember: NetBoxSecurityNatPoolMemberType = (
        strawberry_django.field()
    )
    netbox_nsm_natpoolmember_list: List[NetBoxSecurityNatPoolMemberType] = (
        strawberry_django.field()
    )


@strawberry.type(name="Query")
class NetBoxSecurityNatRuleQuery:
    netbox_nsm_natrule: NetBoxSecurityNatRuleType = strawberry_django.field()
    netbox_nsm_natrule_list: List[NetBoxSecurityNatRuleType] = (
        strawberry_django.field()
    )


@strawberry.type(name="Query")
class NetBoxSecurityNatRuleSetQuery:
    netbox_nsm_natruleset: NetBoxSecurityNatRuleSetType = strawberry_django.field()
    netbox_nsm_natruleset_list: List[NetBoxSecurityNatRuleSetType] = (
        strawberry_django.field()
    )


@strawberry.type(name="Query")
class NetBoxSecurityPolicerQuery:
    netbox_nsm_policer: NetBoxSecurityPolicerType = strawberry_django.field()
    netbox_nsm_policer_list: List[NetBoxSecurityPolicerType] = (
        strawberry_django.field()
    )


@strawberry.type(name="Query")
class NetBoxSecurityFirewallFilterQuery:
    netbox_nsm_firewallfilter: NetBoxSecurityFirewallFilterType = (
        strawberry_django.field()
    )
    netbox_nsm_firewallfilter_list: List[NetBoxSecurityFirewallFilterType] = (
        strawberry_django.field()
    )


@strawberry.type(name="Query")
class NetBoxSecurityFirewallFilterRuleQuery:
    netbox_nsm_firewallfilterrule: NetBoxSecurityFirewallFilterRuleType = (
        strawberry_django.field()
    )
    netbox_nsm_firewallfilterrule_list: List[
        NetBoxSecurityFirewallFilterRuleType
    ] = strawberry_django.field()
