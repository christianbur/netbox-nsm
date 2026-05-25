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
    ApplicationItem,
    Application,
    ApplicationSet,
    ObjectCustomObject,
    SecurityZone,
    SecurityZonePolicyRule,
    SecurityZonePolicyRulebook,
    SecurityZonePolicyRulebookAssignment,
)

__all__ = (
    "SecurityZonePolicyRulebookForm",
    "SecurityZonePolicyRulebookFilterForm",
    "SecurityZonePolicyRulebookBulkEditForm",
    "SecurityZonePolicyRuleForm",
    "SecurityZonePolicyRuleFilterForm",
    "SecurityZonePolicyRulebookAssignmentForm",
    "SecurityZonePolicyRulebookAssignmentFilterForm",
)


class SecurityZonePolicyRulebookForm(PrimaryModelForm):
    name = forms.CharField(max_length=100, required=True)

    fieldsets = (
        FieldSet("name", "rulebook_type", "description", name=_("Rulebook")),
        FieldSet("tags", name=_("Tags")),
    )
    comments = CommentField()

    class Meta:
        model = SecurityZonePolicyRulebook
        fields = (
            "name",
            "rulebook_type",
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

    source_zones = forms.ModelMultipleChoiceField(
        queryset=SecurityZone.objects.all(), required=False
    )
    destination_zones = forms.ModelMultipleChoiceField(
        queryset=SecurityZone.objects.all(), required=False
    )
    services = forms.ModelMultipleChoiceField(
        queryset=ApplicationItem.objects.all(),
        required=False,
        label=_("Service"),
    )
    applications = forms.ModelMultipleChoiceField(
        queryset=Application.objects.all(), required=False
    )
    application_sets = forms.ModelMultipleChoiceField(
        queryset=ApplicationSet.objects.all(), required=False
    )
    log_enabled = forms.BooleanField(required=False, label=_("Log Rules"))

    policy_action = forms.ChoiceField(
        choices=SecurityZonePolicyRule._meta.get_field("policy_action").choices,
        required=True,
        label=_("Action"),
    )
    custom_srcdst_objects = forms.ModelMultipleChoiceField(
        queryset=ObjectCustomObject.objects.filter(custom_type__area="srcdst"),
        required=False,
        label=_("Custom Src/Dst Objects"),
    )
    custom_service_objects = forms.ModelMultipleChoiceField(
        queryset=ObjectCustomObject.objects.filter(custom_type__area="services"),
        required=False,
        label=_("Custom Service Objects"),
    )
    custom_action_objects = forms.ModelMultipleChoiceField(
        queryset=ObjectCustomObject.objects.filter(custom_type__area="action"),
        required=False,
        label=_("Custom Action Objects"),
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
            "source_zones",
            "custom_srcdst_objects",
            name=_("Source"),
        ),
        FieldSet(
            "destination_zones",
            name=_("Destination"),
        ),
        FieldSet("services", "applications", "application_sets", "custom_service_objects", name=_("Service")),
        FieldSet(
            "policy_action",
            "custom_action_objects",
            "log_enabled",
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
            "source_zones",
            "destination_zones",
            "services",
            "applications",
            "application_sets",
            "policy_action",
            "custom_srcdst_objects",
            "custom_service_objects",
            "custom_action_objects",
            "log_enabled",
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
        FieldSet("source_zones_id", "destination_zones_id", name=_("Zones")),
    )

    rulebook_id = DynamicModelMultipleChoiceField(
        queryset=SecurityZonePolicyRulebook.objects.all(),
        required=False,
        label=_("Rulebook"),
    )
    source_zones_id = DynamicModelMultipleChoiceField(
        queryset=SecurityZone.objects.all(),
        required=False,
        label=_("Source Zone"),
    )
    destination_zones_id = DynamicModelMultipleChoiceField(
        queryset=SecurityZone.objects.all(),
        required=False,
        label=_("Destination Zone"),
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
