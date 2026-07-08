"""Forms for Object Link schema configuration."""

from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from netbox_nsm.security.object_link_config.service import get_object_link_config_state


class ObjectLinkConfigForm(forms.Form):
    host_types = forms.MultipleChoiceField(
        label=_("Netbox object (host / inventory)"),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "d-none object-link-config-field"}),
    )
    security_types = forms.MultipleChoiceField(
        label=_("Security object (policy)"),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "d-none object-link-config-field"}),
    )
    allow_destructive = forms.BooleanField(
        label=_("Allow destructive changes"),
        required=False,
        help_text=_(
            "Required when removing types that are still referenced by existing link rows."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        state = get_object_link_config_state()
        if state is None:
            return
        host_choices = [(t["ref"], t["label"]) for t in state["host_types"]]
        security_choices = [(t["ref"], t["label"]) for t in state["security_types"]]
        self.fields["host_types"].choices = host_choices
        self.fields["security_types"].choices = security_choices
        if not self.is_bound:
            self.initial["host_types"] = state["host_refs"]
            self.initial["security_types"] = state["security_refs"]

    def clean(self):
        cleaned = super().clean()
        host = cleaned.get("host_types") or []
        security = cleaned.get("security_types") or []
        if not host:
            raise forms.ValidationError(_("Select at least one Netbox object type."))
        if not security:
            raise forms.ValidationError(_("Select at least one Security object type."))
        return cleaned
