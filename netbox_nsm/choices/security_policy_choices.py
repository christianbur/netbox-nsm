from utilities.choices import ChoiceSet

__all__ = ("ActionChoices",)


class ActionChoices(ChoiceSet):

    PERMIT = "permit"
    DENY = "deny"
    LOG = "log"
    COUNT = "count"
    REJECT = "reject"

    CHOICES = [
        (PERMIT, "Erlauben", "green"),
        (DENY, "Verwerfen", "red"),
        (LOG, "Log", "orange"),
        (COUNT, "Zählen", "orange"),
        (REJECT, "Ablehnen", "red"),
    ]
