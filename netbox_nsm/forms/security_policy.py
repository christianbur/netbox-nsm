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
    SecurityArea,
    SecurityObject,
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
        model = SecurityPolicyRulebook
        fields = (
            "name",
            "rulebook_type",
            "rule_comment_template",
            "description",
            "comments",
            "tags",
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
    enabled = forms.BooleanField(required=False, initial=True, label=_("Status (on/off)"))
    name = forms.CharField(max_length=100, required=True)
    rulebook = DynamicModelChoiceField(
        queryset=SecurityPolicyRulebook.objects.all(), required=True
    )
    area_selections = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        initial="[]",
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
        return instance

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

        area_cache = {a.slug: a for a in SecurityArea.objects.all()}

        for sel in selections:
            if not isinstance(sel, dict):
                continue
            area_slug = str(sel.get("area", "")).strip()
            placement = str(sel.get("placement", "")).strip()
            kind = str(sel.get("kind", "")).strip()
            obj_id = sel.get("id")

            if not area_slug or not placement or not kind or not obj_id:
                continue
            area = area_cache.get(area_slug)
            if not area:
                continue
            if placement not in ("source", "destination", "fixed"):
                continue

            try:
                pk = int(obj_id)
            except (ValueError, TypeError):
                continue

            if kind == "object":
                try:
                    obj = SecurityObject.objects.get(pk=pk)
                except SecurityObject.DoesNotExist:
                    continue
                SecurityPolicyRuleObjectItem.objects.get_or_create(
                    rule=instance, area=area, placement=placement, security_object=obj
                )
            elif kind == "group":
                try:
                    grp = SecurityObjectGroup.objects.get(pk=pk)
                except SecurityObjectGroup.DoesNotExist:
                    continue
                SecurityPolicyRuleGroupItem.objects.get_or_create(
                    rule=instance, area=area, placement=placement, security_group=grp
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
