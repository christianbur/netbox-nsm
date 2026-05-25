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

from netbox_nsm.models import (
    Address,
    Application,
    ApplicationItem,
    ObjectGroup,
    ObjectGroupAssignment,
    SecurityZone,
)

__all__ = (
    "ObjectGroupForm",
    "ObjectGroupFilterForm",
    "ObjectGroupImportForm",
    "ObjectGroupBulkEditForm",
    "ObjectGroupAssignmentForm",
    "ObjectGroupAssignmentFilterForm",
)


class ObjectGroupForm(PrimaryModelForm):
    name = forms.CharField(max_length=100, required=True)
    group_type = forms.ChoiceField(choices=ObjectGroup._meta.get_field("group_type").choices, required=True)
    group_member_type = forms.ChoiceField(
        choices=(("", "---------"),) + ObjectGroup.GROUP_MEMBER_TYPE_CHOICES,
        required=False,
        label=_("Child group object type"),
        help_text=_("Only used when group type is 'Groups'."),
    )
    groups = DynamicModelMultipleChoiceField(
        queryset=ObjectGroup.objects.all(),
        required=False,
        label=_("Subgroups (same type)"),
        help_text=_("Use this to build group hierarchies. Subgroups must have the same group type."),
    )
    addresses = DynamicModelMultipleChoiceField(queryset=Address.objects.all(), required=False)
    services = DynamicModelMultipleChoiceField(queryset=ApplicationItem.objects.all(), required=False)
    applications = DynamicModelMultipleChoiceField(queryset=Application.objects.all(), required=False)
    zones = DynamicModelMultipleChoiceField(queryset=SecurityZone.objects.all(), required=False)
    description = forms.CharField(max_length=200, required=False)

    MEMBER_FIELDS = (
        "groups",
        "addresses",
        "services",
        "applications",
        "zones",
    )

    fieldsets = (
        FieldSet("name", "group_type", "group_member_type", "description", name=_("Group")),
        FieldSet("groups", "addresses", "services", "applications", "zones", name=_("Objekts (src/dst)")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = ObjectGroup
        fields = (
            "name",
            "group_type",
            "group_member_type",
            "groups",
            "addresses",
            "services",
            "applications",
            "zones",
            "description",
            "comments",
            "tags",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mixed groups are intentionally disabled in UI and validation.
        self.fields["group_type"].choices = [
            c for c in self.fields["group_type"].choices if c[0] != "mixed"
        ]

        if self.instance and self.instance.pk:
            self.fields["groups"].queryset = ObjectGroup.objects.exclude(pk=self.instance.pk)

        selected_group_type = self.data.get("group_type") or getattr(self.instance, "group_type", "")
        selected_member_type = self.data.get("group_member_type") or getattr(self.instance, "group_member_type", "")

        if selected_group_type == "groups" and selected_member_type:
            self.fields["groups"].queryset = self.fields["groups"].queryset.filter(group_type=selected_member_type)
        elif selected_group_type in self.MEMBER_FIELDS and selected_group_type != "groups":
            self.fields["groups"].queryset = self.fields["groups"].queryset.filter(group_type=selected_group_type)

        for field_name in self.MEMBER_FIELDS:
            self.fields[field_name].widget.attrs["data-group-member-field"] = field_name

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data is None:
            cleaned_data = self.cleaned_data
        group_type = cleaned_data.get("group_type")
        group_member_type = cleaned_data.get("group_member_type")

        if group_type == "mixed":
            self.add_error("group_type", _("Mixed groups are not supported."))
            return cleaned_data

        if group_type not in self.MEMBER_FIELDS:
            return cleaned_data

        if group_type == "groups":
            if not group_member_type:
                self.add_error("group_member_type", _("Select the object type for child groups."))
            allowed_fields = {"groups"}
        else:
            cleaned_data["group_member_type"] = ""
            allowed_fields = {group_type, "groups"}

        for field_name in self.MEMBER_FIELDS:
            if field_name in allowed_fields:
                continue
            if cleaned_data.get(field_name):
                self.add_error(
                    field_name,
                    _("Only members of the selected group type are allowed."),
                )

        selected_groups = cleaned_data.get("groups") or []
        for nested_group in selected_groups:
            expected_type = group_member_type if group_type == "groups" else group_type
            if nested_group.group_type != expected_type:
                self.add_error(
                    "groups",
                    _("Nested groups must match the configured child group object type."),
                )
                break

        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=commit)
        group_type = self.cleaned_data.get("group_type")
        if not group_type:
            return obj

        allowed_fields = {"groups"} if group_type == "groups" else {group_type, "groups"}

        if group_type != "groups" and obj.group_member_type:
            obj.group_member_type = ""
            obj.save(update_fields=["group_member_type", "last_updated"])

        for field_name in self.MEMBER_FIELDS:
            if field_name in allowed_fields:
                continue
            getattr(obj, field_name).clear()
        return obj


class ObjectGroupFilterForm(PrimaryModelFilterSetForm):
    model = ObjectGroup
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("name", "group_type", name=_("Group")),
    )
    tags = TagFilterField(model)


class ObjectGroupImportForm(PrimaryModelImportForm):
    class Meta:
        model = ObjectGroup
        fields = ("name", "group_type", "description", "tags")


class ObjectGroupBulkEditForm(PrimaryModelBulkEditForm):
    model = ObjectGroup
    group_type = forms.ChoiceField(
        choices=[
            c
            for c in ObjectGroup._meta.get_field("group_type").choices
            if c[0] != "mixed"
        ],
        required=False,
    )
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("group_type", "description"),
        FieldSet("tags", name=_("Tags")),
    )


class ObjectGroupAssignmentForm(forms.ModelForm):
    group = DynamicModelChoiceField(
        label=_("Group"), queryset=ObjectGroup.objects.all()
    )

    fieldsets = (FieldSet(ObjectAttribute("assigned_object"), "group"),)

    class Meta:
        model = ObjectGroupAssignment
        fields = ("group",)

    def clean_group(self):
        group = self.cleaned_data["group"]
        conflicting = ObjectGroupAssignment.objects.filter(
            assigned_object_type=self.instance.assigned_object_type,
            assigned_object_id=self.instance.assigned_object_id,
            group=group,
        )
        if self.instance.id:
            conflicting = conflicting.exclude(id=self.instance.id)
        if conflicting.exists():
            raise forms.ValidationError(_("Assignment already exists"))
        return group


class ObjectGroupAssignmentFilterForm(NetBoxModelFilterSetForm):
    model = ObjectGroupAssignment
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("group_id", name=_("Group")),
        FieldSet("device_id", "virtualdevicecontext_id", "virtualmachine_id", name="Assignments"),
    )
    group_id = DynamicModelMultipleChoiceField(
        queryset=ObjectGroup.objects.all(),
        required=False,
        label=_("Group"),
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
