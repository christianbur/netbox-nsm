from django import forms
from django.contrib.contenttypes.models import ContentType
from django.db import models
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
    AddressList,
    ObjectAction,
    ObjectCustomObject,
    ObjectFilter,
    ObjectGroup,
    ObjectInstalledOn,
    ObjectComment,
    ObjectInterface,
    ObjectNAT,
    ObjectPolicer,
    RulebookTypeChoices,
    SecurityZone,
    SecurityZoneRole,
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
    role = DynamicModelChoiceField(
        queryset=SecurityZoneRole.objects.all(),
        required=False,
        label=_("Security Zone Role"),
    )

    fieldsets = (
        FieldSet("name", "rulebook_type", "role", "description", name=_("Rulebook")),
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        is_create = not (self.instance and self.instance.pk)
        initial_data = self.initial or {}
        if self.instance and self.instance.pk and not self.is_bound:
            initial_data["role"] = self.instance.roles.first()
            self.initial = initial_data

        selected_type = None
        if self.is_bound:
            selected_type = self.data.get("rulebook_type")
        elif self.instance and self.instance.pk:
            selected_type = self.instance.rulebook_type
        else:
            selected_type = initial_data.get("rulebook_type", RulebookTypeChoices.POLICY)

        # Roles are configured after creation (general tab/edit), not on add form.
        if is_create:
            self.fields.pop("role", None)
            return

        if selected_type == RulebookTypeChoices.POLICY:
            self.fields["role"].widget.attrs["disabled"] = "disabled"
            self.fields["role"].help_text = _(
                "Only used for Security Matrix."
            )
        else:
            self.fields["role"].help_text = _(
                "Select the Security Zone Role used for this Security Matrix."
            )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data is None:
            cleaned_data = self.cleaned_data
        if not (self.instance and self.instance.pk):
            return cleaned_data

        rulebook_type = cleaned_data.get("rulebook_type")
        role = cleaned_data.get("role")

        if rulebook_type == RulebookTypeChoices.MATRIX and not role:
            self.add_error(
                "role",
                _("Security Zone Role is required when Rulebook Type is Security Matrix."),
            )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit and "role" in self.fields:
            role = self.cleaned_data.get("role")
            if role:
                instance.roles.set([role])
            else:
                instance.roles.clear()
        return instance


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
    roles = DynamicModelMultipleChoiceField(
        queryset=SecurityZoneRole.objects.all(),
        required=False,
        label=_("Security Zone Roles"),
    )
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("rulebook_type", "roles", "description"),
        FieldSet("tags", name=_("Tags")),
    )


class SecurityZonePolicyRuleForm(PrimaryModelForm):
    GROUP_TYPE_CHOICES = [
        choice
        for choice in ObjectGroup._meta.get_field("group_type").choices
        if choice[0] != "mixed"
    ]

    index = forms.IntegerField(min_value=1, required=True, initial=100)
    enabled = forms.BooleanField(required=False, initial=True, label=_("Status (on/off)"))
    name = forms.CharField(max_length=100, required=True)
    rulebook = DynamicModelChoiceField(
        queryset=SecurityZonePolicyRulebook.objects.all(), required=True
    )

    source_group_types = forms.MultipleChoiceField(
        choices=GROUP_TYPE_CHOICES,
        required=False,
        label=_("Source object types"),
        widget=forms.CheckboxSelectMultiple,
        help_text=_("Filter objects from 'Objekts (src/dst)' by type."),
    )
    source_groups = forms.ModelMultipleChoiceField(
        queryset=ObjectGroup.objects.exclude(group_type="mixed").all(),
        required=False,
        label=_("Source objects"),
        help_text=_("Select one or more objects from 'Objekts (src/dst)'."),
    )
    source_zones = forms.ModelMultipleChoiceField(
        queryset=SecurityZone.objects.all(), required=False
    )
    source_addresses = forms.ModelMultipleChoiceField(
        queryset=AddressList.objects.all(), required=False
    )
    source_zones = forms.ModelMultipleChoiceField(
        queryset=SecurityZone.objects.all(), required=False
    )
    destination_addresses = forms.ModelMultipleChoiceField(
        queryset=AddressList.objects.all(), required=False
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

    object_nat = DynamicModelMultipleChoiceField(
        queryset=ObjectNAT.objects.all(),
        required=False,
        label=_("NAT Objects"),
    )
    object_interface = DynamicModelMultipleChoiceField(
        queryset=ObjectInterface.objects.all(),
        required=False,
        label=_("Interface Objects"),
    )
    object_filter = DynamicModelMultipleChoiceField(
        queryset=ObjectFilter.objects.all(),
        required=False,
        label=_("Filter Objects"),
    )
    object_policer = DynamicModelMultipleChoiceField(
        queryset=ObjectPolicer.objects.all(),
        required=False,
        label=_("Policer Objects"),
    )
    object_comment = DynamicModelMultipleChoiceField(
        queryset=ObjectComment.objects.all(),
        required=False,
        label=_("Comment Objects"),
    )
    object_installed_on = DynamicModelMultipleChoiceField(
        queryset=ObjectInstalledOn.objects.all(),
        required=False,
        label=_("Installed On Objects"),
    )
    log_enabled = forms.BooleanField(required=False, label=_("Log Rules"))

    policy_action = forms.ChoiceField(
        choices=SecurityZonePolicyRule._meta.get_field("policy_action").choices,
        required=True,
        label=_("Action"),
    )
    action_objects = forms.ModelMultipleChoiceField(
        queryset=ObjectAction.objects.all(),
        required=False,
        label=_("Action objects"),
        help_text=_("Select one or more objects from 'Objekte (action)'."),
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
            "source_group_types",
            "source_groups",
            "custom_srcdst_objects",
            "object_nat",
            "object_interface",
            name=_("Source"),
        ),
        FieldSet(
            "destination_group_types",
            "destination_groups",
            name=_("Destination"),
        ),
        FieldSet("services", "applications", "application_sets", "custom_service_objects", name=_("Service")),
        FieldSet(
            "policy_action",
            "action_objects",
            "custom_action_objects",
            "object_filter",
            "object_policer",
            "log_enabled",
            name=_("Objekte (action)"),
        ),
        FieldSet(
            "object_comment",
            "object_installed_on",
            name=_("Info"),
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
            "source_groups",
            "source_zones",
            "source_addresses",
            "destination_groups",
            "destination_zones",
            "destination_addresses",
            "services",
            "applications",
            "application_sets",
            "policy_action",
            "action_objects",
            "custom_srcdst_objects",
            "custom_service_objects",
            "custom_action_objects",
            "object_nat",
            "object_interface",
            "object_filter",
            "object_policer",
            "object_comment",
            "object_installed_on",
            "log_enabled",
            "description",
            "comments",
            "tags",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        counts = {
            row["group_type"]: row["count"]
            for row in (
                ObjectGroup.objects.exclude(group_type="mixed")
                .values("group_type")
                .annotate(count=models.Count("id"))
            )
        }
        counted_choices = [
            (value, f"{label} ({counts.get(value, 0)})")
            for value, label in self.GROUP_TYPE_CHOICES
        ]
        self.fields["source_group_types"].choices = counted_choices
        self.fields["destination_group_types"].choices = counted_choices

        if self.is_bound or not (self.instance and self.instance.pk):
            return

        source_types = list(
            self.instance.source_groups.exclude(group_type="mixed")
            .values_list("group_type", flat=True)
            .distinct()
        )
        destination_types = list(
            self.instance.destination_groups.exclude(group_type="mixed")
            .values_list("group_type", flat=True)
            .distinct()
        )
        self.initial.setdefault("source_group_types", source_types)
        self.initial.setdefault("destination_group_types", destination_types)


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
