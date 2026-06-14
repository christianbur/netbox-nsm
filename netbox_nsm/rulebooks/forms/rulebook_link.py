from django import forms
from django.utils.translation import gettext_lazy as _

from netbox_nsm.rulebooks.registry import iter_deployed_cot_rulebooks

__all__ = ("RulebookLinkAssignForm",)


class RulebookLinkAssignForm(forms.Form):
    rulebook_slug = forms.ChoiceField(
        label=_("Rulebook"),
        choices=(),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = []
        for cot in iter_deployed_cot_rulebooks():
            label = cot.verbose_name or cot.name
            choices.append((cot.slug, label))
        self.fields["rulebook_slug"].choices = choices
