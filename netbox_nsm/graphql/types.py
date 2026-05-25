from typing import Annotated, List

import strawberry
import strawberry_django

from netbox.graphql.types import NetBoxObjectType, PrimaryObjectType
from ipam.graphql.types import IPAddressType, PrefixType, IPRangeType
from tenancy.graphql.types import TenantType

from netbox_nsm.models import (
    ApplicationItem,
    Application,
    ApplicationSet,
    SecurityZone,
)

from .filters import (
    NetBoxSecurityApplicationItemFilter,
    NetBoxSecurityApplicationFilter,
    NetBoxSecurityApplicationSetFilter,
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
    Application, fields="__all__", filters=NetBoxSecurityApplicationFilter
)
class NetBoxSecurityApplicationType(PrimaryObjectType):
    name: str
    identifier: str | None
    tenant: Annotated["TenantType", strawberry.lazy("tenancy.graphql.types")] | None
    application_items: List[
        Annotated[
            "NetBoxSecurityApplicationItemType",
            strawberry.lazy("netbox_nsm.graphql.types"),
        ]
    ]
    protocol: List[str] | None
    destination_ports: List[int] | None
    source_ports: List[int] | None


@strawberry_django.type(
    ApplicationSet, fields="__all__", filters=NetBoxSecurityApplicationSetFilter
)
class NetBoxSecurityApplicationSetType(PrimaryObjectType):
    name: str
    identifier: str | None
    tenant: Annotated["TenantType", strawberry.lazy("tenancy.graphql.types")] | None
    applications: List[
        Annotated[
            "NetBoxSecurityApplicationType",
            strawberry.lazy("netbox_nsm.graphql.types"),
        ]
    ]
    application_sets: List[
        Annotated[
            "NetBoxSecurityApplicationSetType",
            strawberry.lazy("netbox_nsm.graphql.types"),
        ]
    ]


@strawberry_django.type(
    SecurityZone, fields="__all__", filters=NetBoxSecuritySecurityZoneFilter
)
class NetBoxSecuritySecurityZoneType(PrimaryObjectType):
    name: str
    identifier: str | None
    tenant: Annotated["TenantType", strawberry.lazy("tenancy.graphql.types")] | None

