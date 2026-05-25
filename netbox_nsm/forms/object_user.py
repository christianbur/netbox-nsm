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

from netbox_nsm.models import ObjectUser, ObjectUserAssignment

__all__ = (
    "ObjectUserForm",
    "ObjectUserFilterForm",
    "ObjectUserImportForm",
    "ObjectUserBulkEditForm",
    "ObjectUserAssignmentForm",
    "ObjectUserAssignmentFilterForm",
)


class ObjectUserForm(PrimaryModelForm):
    entry_type = forms.ChoiceField(
        choices=ObjectUser._meta.get_field("entry_type").choices,
        required=True,
        label=_("Type"),
    )
    name = forms.CharField(max_length=100, required=True, label=_("Name"))
    dn = forms.CharField(max_length=255, required=True, label=_("Distinguished Name (DN)"))
    description = forms.CharField(max_length=200, required=False)
    fieldsets = (
        FieldSet("name", "entry_type", "dn", "description", name=_("User")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = ObjectUser
        fields = ("name", "entry_type", "dn", "description", "comments", "tags")


class ObjectUserFilterForm(PrimaryModelFilterSetForm):
    model = ObjectUser
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("name", "entry_type", "dn", name=_("User")),
    )
    tags = TagFilterField(model)


class ObjectUserImportForm(PrimaryModelImportForm):
    class Meta:
        model = ObjectUser
        fields = ("name", "entry_type", "dn", "description", "tags")


class ObjectUserBulkEditForm(PrimaryModelBulkEditForm):
    model = ObjectUser
    entry_type = forms.ChoiceField(
        choices=ObjectUser._meta.get_field("entry_type").choices,
        required=False,
        label=_("Type"),
    )
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("entry_type", "description"),
        FieldSet("tags", name=_("Tags")),
    )


class ObjectUserAssignmentForm(forms.ModelForm):
    user = DynamicModelChoiceField(
        label=_("User"), queryset=ObjectUser.objects.all()
    )

    fieldsets = (FieldSet(ObjectAttribute("assigned_object"), "user"),)

    class Meta:
        model = ObjectUserAssignment
        fields = ("user",)

    def clean_user(self):
        user = self.cleaned_data["user"]
        conflicting = ObjectUserAssignment.objects.filter(
            assigned_object_type=self.instance.assigned_object_type,
            assigned_object_id=self.instance.assigned_object_id,
            user=user,
        )
        if self.instance.id:
            conflicting = conflicting.exclude(id=self.instance.id)
        if conflicting.exists():
            raise forms.ValidationError(_("Assignment already exists"))
        return user


class ObjectUserAssignmentFilterForm(NetBoxModelFilterSetForm):
    model = ObjectUserAssignment
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("user_id", name=_("User")),
        FieldSet("device_id", "virtualdevicecontext_id", "virtualmachine_id", name="Assignments"),
    )
    user_id = DynamicModelMultipleChoiceField(
        queryset=ObjectUser.objects.all(),
        required=False,
        label=_("User"),
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
