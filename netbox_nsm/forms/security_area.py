from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import PrimaryModelForm, PrimaryModelFilterSetForm
from utilities.forms.fields import SlugField
from utilities.forms.rendering import FieldSet

from netbox_nsm.models import SecurityArea

__all__ = (
    "SecurityAreaForm",
    "SecurityAreaFilterForm",
)


class SecurityAreaForm(PrimaryModelForm):
    slug = SlugField(
        max_length=50,
        label=_("Slug"),
        help_text=_("Internal identifier (lowercase, no spaces). Cannot be changed after creation."),
    )

    fieldsets = (
        FieldSet("name", "slug", "description", name=_("Area")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = SecurityArea
        fields = ("name", "slug", "description", "tags")


class SecurityAreaFilterForm(PrimaryModelFilterSetForm):
    model = SecurityArea
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
    )
