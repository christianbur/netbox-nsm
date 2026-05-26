from django import forms
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _

from dcim.models import Device, VirtualDeviceContext
from netbox.forms import (
    NetBoxModelFilterSetForm,
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelForm,
)
from utilities.forms.fields import (
    CommentField,
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
    TagFilterField,
)
from utilities.forms.rendering import FieldSet, ObjectAttribute
from virtualization.models import VirtualMachine

from netbox_nsm.models import (
    ObjectCustomObject,
    ObjectGroup,
    SecurityZonePolicyRule,
    SecurityZonePolicyRulebook,
    SecurityZonePolicyRulebookAssignment,
)

__all__ = (
    "SecurityZonePolicyRulebookForm",
    "SecurityZonePolicyRulebookFilterForm",
    "SecurityZonePolicyRulebookBulkEditForm",
    "SecurityZonePolicyRulebookBulkAssignForm",
    "SecurityZonePolicyRuleForm",
    "SecurityZonePolicyRuleFilterForm",
    "SecurityZonePolicyRulebookAssignmentForm",
    "SecurityZonePolicyRulebookAssignmentFilterForm",
)


class SecurityZonePolicyRulebookForm(PrimaryModelForm):
    name = forms.CharField(max_length=100, required=True)
    rule_comment_template = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "## Notes\n\n{rulebook} – Rule #{index}\n"}),
        label=_("Rule Comment Template"),
        help_text=_("Markdown template pre-filled when adding new rules. Supports {rule_name}, {index}, {rulebook}."),
    )

    fieldsets = (
        FieldSet("name", "rulebook_type", "description", name=_("Rulebook")),
        FieldSet("rule_comment_template", name=_("Rule Defaults")),
        FieldSet("tags", name=_("Tags")),
    )
    comments = CommentField()

    class Meta:
        model = SecurityZonePolicyRulebook
        fields = (
            "name",
            "rulebook_type",
            "rule_comment_template",
            "description",
            "comments",
            "tags",
        )



class SecurityZonePolicyRulebookFilterForm(PrimaryModelFilterSetForm):
    model = SecurityZonePolicyRulebook
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("name", "rulebook_type", name=_("Rulebook")),
    )
    tags = TagFilterField(model)


class SecurityZonePolicyRulebookBulkEditForm(PrimaryModelBulkEditForm):
    model = SecurityZonePolicyRulebook
    rulebook_type = forms.ChoiceField(
        choices=SecurityZonePolicyRulebook._meta.get_field("rulebook_type").choices,
        required=False,
    )
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("rulebook_type", "description"),
        FieldSet("tags", name=_("Tags")),
    )


class SecurityZonePolicyRuleForm(PrimaryModelForm):
    index = forms.IntegerField(min_value=1, required=True, initial=100)
    enabled = forms.BooleanField(required=False, initial=True, label=_("Status (on/off)"))
    name = forms.CharField(max_length=100, required=True)
    rulebook = DynamicModelChoiceField(
        queryset=SecurityZonePolicyRulebook.objects.all(), required=True
    )

    custom_srcdst_objects = forms.ModelMultipleChoiceField(
        queryset=ObjectCustomObject.objects.filter(custom_type__area="srcdst"),
        required=False,
        label=_("Source Objects"),
    )
    source_groups = forms.ModelMultipleChoiceField(
        queryset=ObjectGroup.objects.filter(area="srcdst"),
        required=False,
        label=_("Source Groups"),
    )
    destination_custom_objects = forms.ModelMultipleChoiceField(
        queryset=ObjectCustomObject.objects.filter(custom_type__area="srcdst"),
        required=False,
        label=_("Destination Objects"),
    )
    destination_groups = forms.ModelMultipleChoiceField(
        queryset=ObjectGroup.objects.filter(area="srcdst"),
        required=False,
        label=_("Destination Groups"),
    )
    custom_service_objects = forms.ModelMultipleChoiceField(
        queryset=ObjectCustomObject.objects.filter(custom_type__area="services"),
        required=False,
        label=_("Service Objects"),
    )
    service_groups = forms.ModelMultipleChoiceField(
        queryset=ObjectGroup.objects.filter(area="services"),
        required=False,
        label=_("Service Groups"),
    )
    custom_action_objects = forms.ModelMultipleChoiceField(
        queryset=ObjectCustomObject.objects.filter(custom_type__area="action"),
        required=False,
        label=_("Action Objects"),
    )
    action_groups = forms.ModelMultipleChoiceField(
        queryset=ObjectGroup.objects.filter(area="action"),
        required=False,
        label=_("Action Groups"),
    )

    fieldsets = (
        FieldSet(
            "rulebook",
            "index",
            "enabled",
            "name",
            "description",
            name=_("Policy Rule"),
        ),
        FieldSet(
            "custom_srcdst_objects",
            "source_groups",
            name=_("Source"),
        ),
        FieldSet(
            "destination_custom_objects",
            "destination_groups",
            name=_("Destination"),
        ),
        FieldSet(
            "custom_service_objects",
            "service_groups",
            name=_("Service"),
        ),
        FieldSet(
            "custom_action_objects",
            "action_groups",
            name=_("Action"),
        ),
        FieldSet("tags", name=_("Tags")),
    )
    comments = CommentField()

    class Meta:
        model = SecurityZonePolicyRule
        fields = (
            "rulebook",
            "index",
            "enabled",
            "name",
            "custom_srcdst_objects",
            "source_groups",
            "destination_custom_objects",
            "destination_groups",
            "custom_service_objects",
            "service_groups",
            "custom_action_objects",
            "action_groups",
            "description",
            "comments",
            "tags",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class SecurityZonePolicyRuleFilterForm(PrimaryModelFilterSetForm):
    model = SecurityZonePolicyRule
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("rulebook_id", "policy_action", name=_("Policy Rule")),
    )

    rulebook_id = DynamicModelMultipleChoiceField(
        queryset=SecurityZonePolicyRulebook.objects.all(),
        required=False,
        label=_("Rulebook"),
    )
    tags = TagFilterField(model)


class SecurityZonePolicyRulebookAssignmentForm(forms.ModelForm):
    rulebook = DynamicModelChoiceField(
        label=_("Rulebook"), queryset=SecurityZonePolicyRulebook.objects.all()
    )
    fieldsets = (FieldSet(ObjectAttribute("assigned_object"), "rulebook"),)

    class Meta:
        model = SecurityZonePolicyRulebookAssignment
        fields = ("rulebook",)

    def clean_rulebook(self):
        rulebook = self.cleaned_data["rulebook"]
        existing = SecurityZonePolicyRulebookAssignment.objects.filter(
            assigned_object_type=self.instance.assigned_object_type,
            assigned_object_id=self.instance.assigned_object_id,
            rulebook=rulebook,
        )
        if self.instance.id:
            existing = existing.exclude(id=self.instance.id)
        if existing.exists():
            raise forms.ValidationError(_("Assignment already exists"))
        return rulebook


class SecurityZonePolicyRulebookAssignmentFilterForm(NetBoxModelFilterSetForm):
    model = SecurityZonePolicyRulebookAssignment
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("rulebook_id", name=_("Rulebook")),
        FieldSet(
            "device_id",
            "virtualdevicecontext_id",
            "virtualmachine_id",
            name=_("Assignments"),
        ),
    )

    rulebook_id = DynamicModelMultipleChoiceField(
        queryset=SecurityZonePolicyRulebook.objects.all(),
        required=False,
        label=_("Rulebook"),
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


class SecurityZonePolicyRulebookBulkAssignForm(forms.Form):
    """Assign a rulebook to multiple devices/VMs/VDCs in one form submission."""

    devices = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        required=False,
        label=_("Devices"),
    )
    virtual_machines = DynamicModelMultipleChoiceField(
        queryset=VirtualMachine.objects.all(),
        required=False,
        label=_("Virtual Machines"),
    )
    virtual_device_contexts = DynamicModelMultipleChoiceField(
        queryset=VirtualDeviceContext.objects.all(),
        required=False,
        label=_("Virtual Device Contexts"),
    )

    def clean(self):
        data = super().clean()
        if (
            not data.get("devices")
            and not data.get("virtual_machines")
            and not data.get("virtual_device_contexts")
        ):
            raise forms.ValidationError(_("Select at least one device, VM, or VDC."))
        return data
