from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import NetBoxModelFilterSetForm
from utilities.forms.fields import DynamicModelChoiceField, DynamicModelMultipleChoiceField
from utilities.forms.rendering import FieldSet, ObjectAttribute

from netbox_nsm.models import ObjectCustomObject, ObjectCustomObjectAssignment, ObjectCustomType

__all__ = (
    "ObjectCustomObjectAssignmentForm",
    "ObjectCustomObjectAssignmentFilterForm",
)


class ObjectCustomObjectAssignmentForm(forms.ModelForm):
    custom_object = DynamicModelChoiceField(
        label=_("Custom Object"),
        queryset=ObjectCustomObject.objects.all(),
    )

    fieldsets = (FieldSet(ObjectAttribute("assigned_object"), "custom_object"),)

    class Meta:
        model = ObjectCustomObjectAssignment
        fields = ("custom_object",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter custom_object by custom_type if provided via GET param
        custom_type_pk = (self.initial or {}).get("custom_type_pk")
        if custom_type_pk:
            self.fields["custom_object"].queryset = ObjectCustomObject.objects.filter(
                custom_type_id=custom_type_pk
            )
            self.fields["custom_object"].widget.add_query_param(
                "custom_type_id", custom_type_pk
            )

    def clean_custom_object(self):
        custom_object = self.cleaned_data["custom_object"]
        conflicting = ObjectCustomObjectAssignment.objects.filter(
            assigned_object_type=self.instance.assigned_object_type,
            assigned_object_id=self.instance.assigned_object_id,
            custom_object=custom_object,
        )
        if self.instance.id:
            conflicting = conflicting.exclude(id=self.instance.id)
        if conflicting.exists():
            raise forms.ValidationError(_("Assignment already exists"))
        return custom_object


class ObjectCustomObjectAssignmentFilterForm(NetBoxModelFilterSetForm):
    model = ObjectCustomObjectAssignment
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("custom_object_id", name=_("Custom Object")),
    )
    custom_object_id = DynamicModelMultipleChoiceField(
        queryset=ObjectCustomObject.objects.all(),
        required=False,
        label=_("Custom Object"),
    )
