import strawberry

from netbox.graphql.filter_lookups import ArrayLookup

from netbox_nsm.graphql.enums import NetBoxSecurityProtocolEnum


@strawberry.input(
    one_of=True,
    description="Lookup fields. Multiple fields can be set.",
)
class ProtocolArrayLookup(ArrayLookup[NetBoxSecurityProtocolEnum]):
    pass
