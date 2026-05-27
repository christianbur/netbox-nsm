from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelForm,
)
from utilities.forms.fields import TagFilterField, DynamicModelMultipleChoiceField
from utilities.forms.rendering import FieldSet

from netbox_nsm.models import SecurityObjectGroup, SecurityObject
from netbox_nsm.models.security_object_type import AreaChoices

__all__ = (
    "SecurityObjectGroupForm",
    "SecurityObjectGroupFilterForm",
    "SecurityObjectGroupBulkEditForm",
)


class SecurityObjectGroupForm(PrimaryModelForm):
    members = DynamicModelMultipleChoiceField(
        queryset=SecurityObject.objects.all(),
        required=False,
        label=_("Members"),
        query_params={"area": "$area"},
    )
    sub_groups = DynamicModelMultipleChoiceField(
        queryset=SecurityObjectGroup.objects.all(),
        required=False,
        label=_("Sub-Groups"),
        query_params={"area": "$area"},
    )

    fieldsets = (
        FieldSet("name", "area", "description", name=_("Group")),
        FieldSet("members", "sub_groups", name=_("Members")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = SecurityObjectGroup
        fields = ("name", "area", "members", "sub_groups", "description", "comments", "tags")

    def clean_sub_groups(self):
        sub_groups = self.cleaned_data.get("sub_groups", [])
        if self.instance.pk and any(g.pk == self.instance.pk for g in sub_groups):
            raise forms.ValidationError(_("A group cannot be a sub-group of itself."))
        return sub_groups

    def clean(self):
        super().clean()
        area = self.cleaned_data.get("area")
        members = self.cleaned_data.get("members")
        sub_groups = self.cleaned_data.get("sub_groups")
        if area and members:
            bad = [m.name for m in members if m.custom_type.area != area]
            if bad:
                raise forms.ValidationError(
                    _("These members do not match group area '%s': %s") % (area, ", ".join(bad))
                )
        if area and sub_groups:
            bad = [g.name for g in sub_groups if g.area != area]
            if bad:
                raise forms.ValidationError(
                    _("These sub-groups do not match group area '%s': %s") % (area, ", ".join(bad))
                )
        return self.cleaned_data


class SecurityObjectGroupFilterForm(PrimaryModelFilterSetForm):
    model = SecurityObjectGroup
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("area", name=_("Group")),
    )
    area = forms.ChoiceField(
        choices=[("", _("— All —"))] + list(AreaChoices.choices),
        required=False,
    )
    tags = TagFilterField(model)


class SecurityObjectGroupBulkEditForm(PrimaryModelBulkEditForm):
    model = SecurityObjectGroup
    description = forms.CharField(max_length=200, required=False)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("description"),
        FieldSet("tags", name=_("Tags")),
    )
