from django import forms
from django.utils.translation import gettext_lazy as _

from dcim.models import Device, VirtualDeviceContext
from netbox.forms import (
    NetBoxModelFilterSetForm,
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelImportForm,
    PrimaryModelForm,
)
from utilities.forms.fields import (
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
    TagFilterField,
)
from utilities.forms.rendering import FieldSet, ObjectAttribute
from virtualization.models import VirtualMachine

from netbox_nsm.models import ObjectLabel, ObjectLabelAssignment
from netbox_nsm.choices import ObjectLabelTypeChoices

__all__ = (
    "ObjectLabelForm",
    "ObjectLabelFilterForm",
    "ObjectLabelImportForm",
    "ObjectLabelBulkEditForm",
    "ObjectLabelAssignmentForm",
    "ObjectLabelAssignmentFilterForm",
)


class ObjectLabelForm(PrimaryModelForm):
    label_type = forms.ChoiceField(choices=ObjectLabelTypeChoices, required=True, label=_("Type"))
    custom_type = forms.CharField(max_length=100, required=False, label=_("Other label type"))
    name = forms.CharField(max_length=100, required=True)
    color = forms.CharField(
        max_length=7,
        required=True,
        widget=forms.TextInput(attrs={"type": "color"}),
        help_text=_("HTML color code"),
    )
    description = forms.CharField(max_length=200, required=False)
    fieldsets = (
        FieldSet("label_type", "custom_type", "name", "color", "description", name=_("Label")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = ObjectLabel
        fields = ("label_type", "custom_type", "name", "color", "description", "comments", "tags")

    class Media:
        js = ("netbox_nsm/js/object_label_form.js",)

    def clean(self):
        cleaned_data = super().clean() or self.cleaned_data
        label_type = cleaned_data.get("label_type")
        custom_type = (cleaned_data.get("custom_type") or "").strip()
        if label_type == ObjectLabelTypeChoices.OTHER and not custom_type:
            self.add_error("custom_type", _("Custom type is required for 'Other'."))
        if label_type != ObjectLabelTypeChoices.OTHER:
            cleaned_data["custom_type"] = ""
        return cleaned_data


class ObjectLabelFilterForm(PrimaryModelFilterSetForm):
    model = ObjectLabel
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("label_type", "custom_type", "name", "color", name=_("Label")),
    )
    tags = TagFilterField(model)


class ObjectLabelImportForm(PrimaryModelImportForm):
    class Meta:
        model = ObjectLabel
        fields = ("label_type", "custom_type", "name", "color", "description", "tags")


class ObjectLabelBulkEditForm(PrimaryModelBulkEditForm):
    model = ObjectLabel
    label_type = forms.ChoiceField(choices=ObjectLabelTypeChoices, required=False, label=_("Type"))
    custom_type = forms.CharField(max_length=100, required=False, label=_("Other label type"))
    color = forms.CharField(max_length=7, required=False, widget=forms.TextInput(attrs={"type": "color"}))
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("label_type", "custom_type", "color", "description"),
        FieldSet("tags", name=_("Tags")),
    )


class ObjectLabelAssignmentForm(forms.ModelForm):
    label = DynamicModelChoiceField(
        label=_("Label"), queryset=ObjectLabel.objects.all()
    )

    fieldsets = (FieldSet(ObjectAttribute("assigned_object"), "label"),)

    class Meta:
        model = ObjectLabelAssignment
        fields = ("label",)

    def clean_label(self):
        label = self.cleaned_data["label"]
        conflicting = ObjectLabelAssignment.objects.filter(
            assigned_object_type=self.instance.assigned_object_type,
            assigned_object_id=self.instance.assigned_object_id,
            label=label,
        )
        if self.instance.id:
            conflicting = conflicting.exclude(id=self.instance.id)
        if conflicting.exists():
            raise forms.ValidationError(_("Assignment already exists"))
        return label


class ObjectLabelAssignmentFilterForm(NetBoxModelFilterSetForm):
    model = ObjectLabelAssignment
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("label_id", name=_("Label")),
        FieldSet("device_id", "virtualdevicecontext_id", "virtualmachine_id", name="Assignments"),
    )
    label_id = DynamicModelMultipleChoiceField(
        queryset=ObjectLabel.objects.all(),
        required=False,
        label=_("Label"),
    )
    device_id = DynamicModelChoiceField(
        queryset=Device.objects.all(),
        required=False,
        label=_("Device"),
    )
    virtualdevicecontext_id = DynamicModelChoiceField(
        queryset=VirtualDeviceContext.objects.all(),
        required=False,
        query_params={"device_id": "$device_id"},
        label=_("Virtual Device Context"),
    )
    virtualmachine_id = DynamicModelChoiceField(
        queryset=VirtualMachine.objects.all(),
        required=False,
        label=_("Virtual Machine"),
    )
