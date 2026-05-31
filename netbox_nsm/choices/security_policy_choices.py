from django.utils.translation import gettext_lazy as _
from utilities.choices import ChoiceSet

__all__ = ("ActionChoices",)


class ActionChoices(ChoiceSet):

    PERMIT = "permit"
    DENY = "deny"
    LOG = "log"
    COUNT = "count"
    REJECT = "reject"

    CHOICES = [
        (PERMIT, _("Permit"), "green"),
        (DENY, _("Deny"), "red"),
        (LOG, _("Log"), "orange"),
        (COUNT, _("Count"), "orange"),
        (REJECT, _("Reject"), "red"),
    ]
