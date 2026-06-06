from django import forms
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
import json

from dcim.models import Device, Platform, VirtualDeviceContext
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
    ObjectGroup,
    Rule,
    Rulebook,
    RulebookAssignment,
    RuleObjectItem,
    RuleGroupItem,
)
from netbox_nsm.branch_db import (
    branch_aware_manager,
    branch_aware_related,
    branch_db_alias,
    branch_save_instance,
    ensure_branch_context,
    router_write_alias,
    required_junction_db_alias,
    resolve_db_alias,
    use_db_alias,
    junction_transaction,
    pin_instance_db_alias,
)

__all__ = (
    "RulebookForm",
    "RulebookFilterForm",
    "RulebookBulkEditForm",
    "RulebookBulkAssignForm",
    "RuleForm",
    "RuleFilterForm",
    "RulebookAssignmentForm",
    "RulebookAssignmentFilterForm",
)


class RulebookForm(PrimaryModelForm):
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
    platform = DynamicModelChoiceField(
        queryset=Platform.objects.all(),
        required=False,
        label=_("Platform"),
        help_text=_(
            "Firewall platform or security fabric (e.g. PAN-OS, Cisco ASA, TrustSec, Zscaler)."
        ),
    )

    fieldsets = (
        FieldSet(
            "name",
            "rulebook_type",
            "platform",
            "mgmt_url",
            "description",
            name=_("Rulebook"),
        ),
        FieldSet("assigned_devices", "assigned_vms", name=_("Assigned Objects")),
        FieldSet("rule_comment_template", name=_("Rule Defaults")),
        FieldSet("tags", name=_("Tags")),
    )
    comments = CommentField()

    class Meta:
        model = Rulebook
        fields = (
            "name",
            "rulebook_type",
            "platform",
            "mgmt_url",
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
            device_pks = list(
                self.instance.assignments.filter(
                    assigned_object_type=device_ct
                ).values_list("assigned_object_id", flat=True)
            )
            vm_pks = list(
                self.instance.assignments.filter(
                    assigned_object_type=vm_ct
                ).values_list("assigned_object_id", flat=True)
            )
            self.initial["assigned_devices"] = device_pks
            self.initial["assigned_vms"] = vm_pks

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            self._save_assignments(instance)
        return instance

    def _save_assignments(self, instance):
        from django.contrib.contenttypes.models import ContentType
        from netbox_nsm.models import RulebookAssignment

        device_ct = ContentType.objects.get_for_model(Device)
        vm_ct = ContentType.objects.get_for_model(VirtualMachine)
        instance.assignments.filter(
            assigned_object_type__in=[device_ct, vm_ct]
        ).delete()
        for device in self.cleaned_data.get("assigned_devices") or []:
            RulebookAssignment.objects.get_or_create(
                rulebook=instance,
                assigned_object_type=device_ct,
                assigned_object_id=device.pk,
            )
        for vm in self.cleaned_data.get("assigned_vms") or []:
            RulebookAssignment.objects.get_or_create(
                rulebook=instance,
                assigned_object_type=vm_ct,
                assigned_object_id=vm.pk,
            )


class RulebookFilterForm(PrimaryModelFilterSetForm):
    model = Rulebook
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("name", "rulebook_type", name=_("Rulebook")),
    )
    tags = TagFilterField(model)


class RulebookBulkEditForm(PrimaryModelBulkEditForm):
    model = Rulebook
    rulebook_type = forms.ChoiceField(
        choices=Rulebook._meta.get_field("rulebook_type").choices,
        required=False,
    )
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("rulebook_type", "description"),
        FieldSet("tags", name=_("Tags")),
    )


class RuleForm(PrimaryModelForm):
    ENABLED_CHOICES = (
        ("1", _("On")),
        ("0", _("Off")),
    )

    index = forms.IntegerField(min_value=1, required=True, initial=100)
    enabled = forms.ChoiceField(
        choices=ENABLED_CHOICES,
        required=True,
        label=_("Status"),
        widget=forms.Select(attrs={"class": "form-select"}),
        initial="1",
    )
    name = forms.CharField(max_length=100, required=True)
    rulebook = DynamicModelChoiceField(queryset=Rulebook.objects.all(), required=True)
    area_selections = forms.CharField(
        widget=forms.HiddenInput(attrs={"id": "nsm-area-selections"}),
        required=False,
        initial="[]",
    )
    virtual_group_config = forms.CharField(
        widget=forms.HiddenInput(attrs={"id": "nsm-virtual-group-config"}),
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
            name=_("Security Rule"),
        ),
        FieldSet("tags", name=_("Tags")),
    )
    comments = CommentField()

    class Meta:
        model = Rule
        fields = (
            "rulebook",
            "index",
            "enabled",
            "name",
            "description",
            "comments",
            "tags",
        )

    def __init__(self, *args, request=None, **kwargs):
        self._request = request
        self._db_alias = None
        super().__init__(*args, **kwargs)
        if request is not None:
            self._db_alias = resolve_db_alias(instance=self.instance, request=request)
        if self.instance.pk:
            self.fields["enabled"].initial = "1" if self.instance.enabled else "0"
            self.fields["rulebook"].disabled = True
        elif self.is_bound:
            pass
        else:
            self.fields["enabled"].initial = "1"

    def clean_rulebook(self):
        if self.instance.pk:
            return self.instance.rulebook
        return self.cleaned_data.get("rulebook")

    def clean_enabled(self):
        return self.cleaned_data.get("enabled") == "1"

    def save(self, commit=True):
        req = self._request
        with ensure_branch_context(req):
            alias = (
                router_write_alias(Rule)
                or branch_db_alias()
                or self._db_alias
                or resolve_db_alias(instance=self.instance, request=req)
            )
            with use_db_alias(alias):
                if alias and not self.instance.pk:
                    self.instance._state.db = alias
                instance = super().save(commit=commit)
                if commit:
                    # super().save() may clear active_branch; re-activate for junction rows.
                    with ensure_branch_context(req):
                        db_alias = required_junction_db_alias(instance, req, hint=alias)
                        if db_alias:
                            instance._state.db = db_alias
                        pin_instance_db_alias(instance, req)
                        self._save_area_selections(instance, db_alias=db_alias)
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
        current = instance.virtual_group_config or {}
        if clean == current:
            return
        instance.virtual_group_config = clean
        branch_save_instance(
            instance, request=self._request, update_fields=["virtual_group_config"]
        )

    def _save_area_selections(self, instance, db_alias=None):
        """Parse area_selections JSON and create/update RuleObjectItem and RuleGroupItem."""
        req = self._request
        with ensure_branch_context(req):
            db_alias = required_junction_db_alias(instance, req, hint=db_alias)
            with use_db_alias(db_alias):
                self._write_area_selections(instance, req, db_alias)

    def _write_area_selections(self, instance, req, db_alias=None):
        raw = self.cleaned_data.get("area_selections", "[]") or "[]"
        try:
            selections = json.loads(raw)
        except (ValueError, TypeError):
            selections = []

        if not isinstance(selections, list):
            selections = []

        # Delete old items and re-create from submitted selections
        branch_aware_related(
            instance.object_items, instance, req, db_alias=db_alias
        ).all().delete()
        branch_aware_related(
            instance.group_items, instance, req, db_alias=db_alias
        ).all().delete()

        # Build RulebookField lookup: slug → field (scoped to this rulebook)
        field_cache = {
            f.slug: f
            for f in branch_aware_manager(
                RulebookField, instance, req, db_alias=db_alias
            ).filter(rulebook=instance.rulebook)
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
                item_mgr = branch_aware_manager(
                    RuleObjectItem, instance, req, db_alias=db_alias
                )
                lookup = {
                    "rule_id": instance.pk,
                    "field_id": field.pk,
                    "content_type_id": ct_id,
                    "object_id": real_obj_id,
                }
                if not item_mgr.filter(**lookup).exists():
                    RuleObjectItem(**lookup, exclude=exclude).save(using=db_alias)
                else:
                    item_mgr.filter(**lookup).update(exclude=exclude)
            elif kind == "group":
                try:
                    pk = int(obj_id)
                except (ValueError, TypeError):
                    continue
                try:
                    grp = branch_aware_manager(
                        ObjectGroup, instance, req, db_alias=db_alias
                    ).get(pk=pk)
                except ObjectGroup.DoesNotExist:
                    continue
                exclude = bool(sel.get("exclude", False))
                grp_mgr = branch_aware_manager(
                    RuleGroupItem, instance, req, db_alias=db_alias
                )
                lookup = {
                    "rule_id": instance.pk,
                    "field_id": field.pk,
                    "security_group": grp,
                }
                if not grp_mgr.filter(**lookup).exists():
                    RuleGroupItem(**lookup, exclude=exclude).save(using=db_alias)
                else:
                    grp_mgr.filter(**lookup).update(exclude=exclude)


class RuleFilterForm(PrimaryModelFilterSetForm):
    model = Rule
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("rulebook_id", name=_("Policy Rule")),
    )

    rulebook_id = DynamicModelMultipleChoiceField(
        queryset=Rulebook.objects.all(),
        required=False,
        label=_("Rulebook"),
    )
    tags = TagFilterField(model)


class RulebookAssignmentForm(forms.ModelForm):
    rulebook = DynamicModelChoiceField(
        label=_("Rulebook"), queryset=Rulebook.objects.all()
    )
    fieldsets = (FieldSet(ObjectAttribute("assigned_object"), "rulebook"),)

    class Meta:
        model = RulebookAssignment
        fields = ("rulebook",)

    def clean_rulebook(self):
        rulebook = self.cleaned_data["rulebook"]
        existing = RulebookAssignment.objects.filter(
            assigned_object_type=self.instance.assigned_object_type,
            assigned_object_id=self.instance.assigned_object_id,
            rulebook=rulebook,
        )
        if self.instance.id:
            existing = existing.exclude(id=self.instance.id)
        if existing.exists():
            raise forms.ValidationError(_("Assignment already exists"))
        return rulebook


class RulebookAssignmentFilterForm(NetBoxModelFilterSetForm):
    model = RulebookAssignment
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
        queryset=Rulebook.objects.all(),
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


class RulebookBulkAssignForm(forms.Form):
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
