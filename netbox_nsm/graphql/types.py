from typing import Annotated, List

import strawberry
import strawberry_django

from netbox.graphql.types import NetBoxObjectType, PrimaryObjectType
from ipam.graphql.types import IPAddressType, PrefixType, IPRangeType
from tenancy.graphql.types import TenantType

from netbox_nsm.models import (
    CustomPrefix,
    Address,
    AddressSet,
    AddressList,
    ApplicationItem,
    Application,
    ApplicationSet,
    SecurityZone,
)

from .filters import (
    NetBoxSecurityCustomPrefixFilter,
    NetBoxSecurityAddressFilter,
    NetBoxSecurityAddressSetFilter,
    NetBoxSecurityAddressListFilter,
    NetBoxSecurityApplicationItemFilter,
    NetBoxSecurityApplicationFilter,
    NetBoxSecurityApplicationSetFilter,
    NetBoxSecuritySecurityZoneFilter,
)


@strawberry_django.type(
    CustomPrefix, fields="__all__", filters=NetBoxSecurityCustomPrefixFilter
)
class NetBoxSecurityCustomPrefixType(PrimaryObjectType):
    tenant: Annotated["TenantType", strawberry.lazy("tenancy.graphql.types")] | None
    prefix: str | None


@strawberry_django.type(
    Address,
    exclude=["assigned_object_type", "assigned_object_id"],
    filters=NetBoxSecurityAddressFilter,
)
class NetBoxSecurityAddressType(PrimaryObjectType):
    tenant: Annotated["TenantType", strawberry.lazy("tenancy.graphql.types")] | None
    name: str
    identifier: str | None
    dns_name: str | None

    @strawberry_django.field(prefetch_related="assigned_object")
    def assigned_object(self) -> (
        Annotated[
            Annotated["IPAddressType", strawberry.lazy("ipam.graphql.types")]
            | Annotated["PrefixType", strawberry.lazy("ipam.graphql.types")]
            | Annotated["IPRangeType", strawberry.lazy("ipam.graphql.types")]
            | Annotated[
                "NetBoxSecurityCustomPrefixType",
                strawberry.lazy("netbox_nsm.graphql.types"),
            ],
            strawberry.union("AddressAssignmentType"),
        ]
        | None
    ):
        return self.assigned_object


@strawberry_django.type(
    AddressSet, fields="__all__", filters=NetBoxSecurityAddressSetFilter
)
class NetBoxSecurityAddressSetType(PrimaryObjectType):
    tenant: Annotated["TenantType", strawberry.lazy("tenancy.graphql.types")] | None
    name: str
    identifier: str | None
    addresses: List[
        Annotated[
            "NetBoxSecurityAddressType",
            strawberry.lazy("netbox_nsm.graphql.types"),
        ]
    ]
    address_sets: List[
        Annotated[
            "NetBoxSecurityAddressSetType",
            strawberry.lazy("netbox_nsm.graphql.types"),
        ]
    ]


@strawberry_django.type(
    AddressList, fields="__all__", filters=NetBoxSecurityAddressListFilter
)
class NetBoxSecurityAddressListType(NetBoxObjectType):
    tenant: Annotated["TenantType", strawberry.lazy("tenancy.graphql.types")] | None
    name: str
    value: str


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

