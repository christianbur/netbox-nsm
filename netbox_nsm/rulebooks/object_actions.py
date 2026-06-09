"""Object actions for COT-backed rulebook list views."""

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.object_actions import ObjectAction

__all__ = ("AddCotRulebook",)


class AddCotRulebook(ObjectAction):
    """Open the COT rulebook creation wizard."""

    label = _("Add")
    template_name = "buttons/add.html"

    @classmethod
    def get_url(cls, obj):
        return reverse("plugins:netbox_nsm:cot_rulebook_add")
