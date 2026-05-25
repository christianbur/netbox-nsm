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

from netbox_nsm.models import ObjectSGT, ObjectSGTAssignment

__all__ = (
    "ObjectSGTForm",
    "ObjectSGTFilterForm",
    "ObjectSGTImportForm",
    "ObjectSGTBulkEditForm",
    "ObjectSGTAssignmentForm",
    "ObjectSGTAssignmentFilterForm",
)


class ObjectSGTForm(PrimaryModelForm):
    name = forms.CharField(max_length=100, required=True)
    tag = forms.IntegerField(required=False)
    color = forms.CharField(max_length=20, required=True)
    description = forms.CharField(max_length=200, required=False)
    fieldsets = (
        FieldSet("name", "tag", "color", "description", name=_("SGT")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = ObjectSGT
        fields = ("name", "tag", "color", "description", "comments", "tags")


class ObjectSGTFilterForm(PrimaryModelFilterSetForm):
    model = ObjectSGT
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("name", "tag", "color", name=_("SGT")),
    )
    tags = TagFilterField(model)


class ObjectSGTImportForm(PrimaryModelImportForm):
    class Meta:
        model = ObjectSGT
        fields = ("name", "tag", "color", "description", "tags")


class ObjectSGTBulkEditForm(PrimaryModelBulkEditForm):
    model = ObjectSGT
    tag = forms.IntegerField(required=False)
    color = forms.CharField(max_length=20, required=False)
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description", "tag"]
    fieldsets = (
        FieldSet("tag", "color", "description"),
        FieldSet("tags", name=_("Tags")),
    )


class ObjectSGTAssignmentForm(forms.ModelForm):
    sgt = DynamicModelChoiceField(
        label=_("SGT"), queryset=ObjectSGT.objects.all()
    )

    fieldsets = (FieldSet(ObjectAttribute("assigned_object"), "sgt"),)

    class Meta:
        model = ObjectSGTAssignment
        fields = ("sgt",)

    def clean_sgt(self):
        sgt = self.cleaned_data["sgt"]
        conflicting = ObjectSGTAssignment.objects.filter(
            assigned_object_type=self.instance.assigned_object_type,
            assigned_object_id=self.instance.assigned_object_id,
            sgt=sgt,
        )
        if self.instance.id:
            conflicting = conflicting.exclude(id=self.instance.id)
        if conflicting.exists():
            raise forms.ValidationError(_("Assignment already exists"))
        return sgt


class ObjectSGTAssignmentFilterForm(NetBoxModelFilterSetForm):
    model = ObjectSGTAssignment
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("sgt_id", name=_("SGT")),
        FieldSet("device_id", "virtualdevicecontext_id", "virtualmachine_id", name="Assignments"),
    )
    sgt_id = DynamicModelMultipleChoiceField(
        queryset=ObjectSGT.objects.all(),
        required=False,
        label=_("SGT"),
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
