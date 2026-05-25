from .nat_pool_choices import PoolTypeChoices
from .nat_rule_choices import (
    AddressTypeChoices,
    CustomInterfaceChoices,
    NatTypeChoices,
    RuleDirectionChoices,
    RuleStatusChoices,
)
from .security_policy_choices import ActionChoices
from utilities.choices import ChoiceSet


class FamilyChoices(ChoiceSet):
    INET = "inet"
    INET6 = "inet6"
    ANY = "any"
    MPLS = "mpls"
    CCC = "ccc"

    CHOICES = [
        (INET, "INET", "green"),
        (INET6, "INET6", "red"),
        (ANY, "ANY", "blue"),
        (MPLS, "MPLS", "cyan"),
        (CCC, "CCC", "orange"),
    ]
from .policer_choices import ForwardingClassChoices, LossPriorityChoices
from .application_choices import ProtocolChoices

__all__ = [
    "AddressTypeChoices",
    "CustomInterfaceChoices",
    "NatTypeChoices",
    "RuleStatusChoices",
    "ActionChoices",
    "PoolTypeChoices",
    "RuleDirectionChoices",
    "FamilyChoices",
    "ForwardingClassChoices",
    "LossPriorityChoices",
    "ProtocolChoices",
]
