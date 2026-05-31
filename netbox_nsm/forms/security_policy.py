from django import forms
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
import json

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
    RulebookField,
    SecurityArea,
    SecurityObjectGroup,
    SecurityPolicyRule,
    SecurityPolicyRulebook,
    SecurityPolicyAssignment,
    SecurityPolicyRuleObjectItem,
    SecurityPolicyRuleGroupItem,
)

__all__ = (
    "SecurityPolicyRulebookForm",
    "SecurityPolicyRulebookFilterForm",
    "SecurityPolicyRulebookBulkEditForm",
    "SecurityPolicyRulebookBulkAssignForm",
    "SecurityPolicyRuleForm",
    "SecurityPolicyRuleFilterForm",
    "SecurityPolicyAssignmentForm",
    "SecurityPolicyAssignmentFilterForm",
)


class SecurityPolicyRulebookForm(PrimaryModelForm):
    name = forms.CharField(max_length=100, required=True)
    rule_comment_template = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 5, "placeholder": "## Notes\n\n{rulebook} – Rule #{index}\n"}
        ),
        label=_("Rule Comment Template"),
        help_text=_(
            "Markdown template pre-filled when adding new rules. Supports {rule_name}, {index}, {rulebook}."
        ),
    )
    assigned_devices = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        required=False,
        label=_("Assigned Devices"),
    )
    assigned_vms = DynamicModelMultipleChoiceField(
        queryset=VirtualMachine.objects.all(),
        required=False,
        label=_("Assigned Virtual Machines"),
    )

    fieldsets = (
        FieldSet("name", "rulebook_type", "description", name=_("Rulebook")),
        FieldSet("assigned_devices", "assigned_vms", name=_("Assigned Objects")),
        FieldSet("rule_comment_template", name=_("Rule Defaults")),
        FieldSet("tags", name=_("Tags")),
    )
    comments = CommentField()

    class Meta:
        model = SecurityPolicyRulebook
        fields = (
            "name",
            "rulebook_type",
            "rule_comment_template",
            "description",
            "comments",
            "tags",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            from django.contrib.contenttypes.models import ContentType
            device_ct = ContentType.objects.get_for_model(Device)
            vm_ct = ContentType.objects.get_for_model(VirtualMachine)
            device_pks = list(self.instance.assignments.filter(
                assigned_object_type=device_ct
            ).values_list("assigned_object_id", flat=True))
            vm_pks = list(self.instance.assignments.filter(
                assigned_object_type=vm_ct
            ).values_list("assigned_object_id", flat=True))
            self.initial["assigned_devices"] = device_pks
            self.initial["assigned_vms"] = vm_pks

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            self._save_assignments(instance)
        return instance

    def _save_assignments(self, instance):
        from django.contrib.contenttypes.models import ContentType
        from netbox_nsm.models import SecurityPolicyAssignment
        device_ct = ContentType.objects.get_for_model(Device)
        vm_ct = ContentType.objects.get_for_model(VirtualMachine)
        instance.assignments.filter(
            assigned_object_type__in=[device_ct, vm_ct]
        ).delete()
        for device in self.cleaned_data.get("assigned_devices") or []:
            SecurityPolicyAssignment.objects.get_or_create(
                rulebook=instance,
                assigned_object_type=device_ct,
                assigned_object_id=device.pk,
            )
        for vm in self.cleaned_data.get("assigned_vms") or []:
            SecurityPolicyAssignment.objects.get_or_create(
                rulebook=instance,
                assigned_object_type=vm_ct,
                assigned_object_id=vm.pk,
            )


class SecurityPolicyRulebookFilterForm(PrimaryModelFilterSetForm):
    model = SecurityPolicyRulebook
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("name", "rulebook_type", name=_("Rulebook")),
    )
    tags = TagFilterField(model)


class SecurityPolicyRulebookBulkEditForm(PrimaryModelBulkEditForm):
    model = SecurityPolicyRulebook
    rulebook_type = forms.ChoiceField(
        choices=SecurityPolicyRulebook._meta.get_field("rulebook_type").choices,
        required=False,
    )
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("rulebook_type", "description"),
        FieldSet("tags", name=_("Tags")),
    )


class SecurityPolicyRuleForm(PrimaryModelForm):
    index = forms.IntegerField(min_value=1, required=True, initial=100)
    enabled = forms.BooleanField(
        required=False, initial=True, label=_("Status (on/off)")
    )
    name = forms.CharField(max_length=100, required=True)
    rulebook = DynamicModelChoiceField(
        queryset=SecurityPolicyRulebook.objects.all(), required=True
    )
    area_selections = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        initial="[]",
    )
    virtual_group_config = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        initial="{}",
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
        FieldSet("tags", name=_("Tags")),
    )
    comments = CommentField()

    class Meta:
        model = SecurityPolicyRule
        fields = (
            "rulebook",
            "index",
            "enabled",
            "name",
            "description",
            "comments",
            "tags",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            self._save_area_selections(instance)
            self._save_virtual_group_config(instance)
        return instance

    def _save_virtual_group_config(self, instance):
        """Parse virtual_group_config JSON and save to rule.virtual_group_config.
        Format: {area_slug: true} — true means all items in that area form one AND-group.
        """
        raw = self.cleaned_data.get("virtual_group_config", "{}") or "{}"
        try:
            config = json.loads(raw)
        except (ValueError, TypeError):
            config = {}
        if not isinstance(config, dict):
            config = {}
        # Keep only areas where value is truthy
        clean = {str(k): True for k, v in config.items() if v}
        instance.virtual_group_config = clean
        instance.save(update_fields=["virtual_group_config"])

    def _save_area_selections(self, instance):
        """Parse area_selections JSON and create/update SecurityPolicyRuleObjectItem and SecurityPolicyRuleGroupItem."""
        raw = self.cleaned_data.get("area_selections", "[]") or "[]"
        try:
            selections = json.loads(raw)
        except (ValueError, TypeError):
            selections = []

        if not isinstance(selections, list):
            selections = []

        # Delete old items and re-create from submitted selections
        instance.object_items.all().delete()
        instance.group_items.all().delete()

        # Build RulebookField lookup: slug → field (scoped to this rulebook)
        field_cache = {
            f.slug: f
            for f in RulebookField.objects.filter(rulebook=instance.rulebook)
        }

        for sel in selections:
            if not isinstance(sel, dict):
                continue
            area_slug = str(sel.get("area", "")).strip()
            kind = str(sel.get("kind", "")).strip()
            obj_id = sel.get("id")

            if not area_slug or not kind or not obj_id:
                continue
            field = field_cache.get(area_slug)
            if not field:
                continue

            if kind == "object":
                parts = str(obj_id).split(".", 1)
                if len(parts) != 2:
                    continue
                try:
                    ct_id, real_obj_id = int(parts[0]), int(parts[1])
                except (ValueError, TypeError):
                    continue
                exclude = bool(sel.get("exclude", False))
                SecurityPolicyRuleObjectItem.objects.get_or_create(
                    rule=instance,
                    field=field,
                    content_type_id=ct_id,
                    object_id=real_obj_id,
                    defaults={"exclude": exclude},
                )
            elif kind == "group":
                try:
                    pk = int(obj_id)
                except (ValueError, TypeError):
                    continue
                try:
                    grp = SecurityObjectGroup.objects.get(pk=pk)
                except SecurityObjectGroup.DoesNotExist:
                    continue
                exclude = bool(sel.get("exclude", False))
                SecurityPolicyRuleGroupItem.objects.get_or_create(
                    rule=instance,
                    field=field,
                    security_group=grp,
                    defaults={"exclude": exclude},
                )


class SecurityPolicyRuleFilterForm(PrimaryModelFilterSetForm):
    model = SecurityPolicyRule
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("rulebook_id", "policy_action", name=_("Policy Rule")),
    )

    rulebook_id = DynamicModelMultipleChoiceField(
        queryset=SecurityPolicyRulebook.objects.all(),
        required=False,
        label=_("Rulebook"),
    )
    tags = TagFilterField(model)


class SecurityPolicyAssignmentForm(forms.ModelForm):
    rulebook = DynamicModelChoiceField(
        label=_("Rulebook"), queryset=SecurityPolicyRulebook.objects.all()
    )
    fieldsets = (FieldSet(ObjectAttribute("assigned_object"), "rulebook"),)

    class Meta:
        model = SecurityPolicyAssignment
        fields = ("rulebook",)

    def clean_rulebook(self):
        rulebook = self.cleaned_data["rulebook"]
        existing = SecurityPolicyAssignment.objects.filter(
            assigned_object_type=self.instance.assigned_object_type,
            assigned_object_id=self.instance.assigned_object_id,
            rulebook=rulebook,
        )
        if self.instance.id:
            existing = existing.exclude(id=self.instance.id)
        if existing.exists():
            raise forms.ValidationError(_("Assignment already exists"))
        return rulebook


class SecurityPolicyAssignmentFilterForm(NetBoxModelFilterSetForm):
    model = SecurityPolicyAssignment
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
        queryset=SecurityPolicyRulebook.objects.all(),
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


class SecurityPolicyRulebookBulkAssignForm(forms.Form):
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
