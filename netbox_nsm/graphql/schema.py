from typing import List

import strawberry
import strawberry_django

from .types import (
    NetBoxSecurityApplicationItemType,
    NetBoxSecuritySecurityZoneType,
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
class NetBoxSecuritySecurityZoneQuery:
    netbox_nsm_securityzone: NetBoxSecuritySecurityZoneType = (
        strawberry_django.field()
    )
    netbox_nsm_securityzone_list: List[NetBoxSecuritySecurityZoneType] = (
        strawberry_django.field()
    )

