import strawberry

from netbox_nsm.choices import (
    FamilyChoices,
    ActionChoices,
    ProtocolChoices,
)

__all__ = (
    "NetBoxSecurityFamilyEnum",
    "NetBoxSecurityActionEnum",
    "NetBoxSecurityProtocolEnum",
)


NetBoxSecurityFamilyEnum = strawberry.enum(FamilyChoices.as_enum())
NetBoxSecurityActionEnum = strawberry.enum(ActionChoices.as_enum())
NetBoxSecurityProtocolEnum = strawberry.enum(ProtocolChoices.as_enum())
