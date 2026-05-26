from typing import Annotated, List

import strawberry
import strawberry_django

from netbox.graphql.types import NetBoxObjectType, PrimaryObjectType
from ipam.graphql.types import IPAddressType, PrefixType, IPRangeType
from tenancy.graphql.types import TenantType

from netbox_nsm.models import (
    ApplicationItem,
    SecurityZone,
)

from .filters import (
    NetBoxSecurityApplicationItemFilter,
    NetBoxSecuritySecurityZoneFilter,
)


@strawberry_django.type(
    ApplicationItem, fields="__all__", filters=NetBoxSecurityApplicationItemFilter
)
class NetBoxSecurityApplicationItemType(PrimaryObjectType):
    name: str
    index: int
    protocol: List[str] | None
    destination_ports: List[int] | None
    source_ports: List[int] | None


@strawberry_django.type(
    SecurityZone, fields="__all__", filters=NetBoxSecuritySecurityZoneFilter
)
class NetBoxSecuritySecurityZoneType(PrimaryObjectType):
    name: str
    identifier: str | None
    tenant: Annotated["TenantType", strawberry.lazy("tenancy.graphql.types")] | None

