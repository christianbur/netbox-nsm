import strawberry

from netbox_nsm.choices.application_choices import ProtocolChoices

__all__ = ("NetBoxSecurityProtocolEnum",)

NetBoxSecurityProtocolEnum = strawberry.enum(ProtocolChoices.as_enum())
