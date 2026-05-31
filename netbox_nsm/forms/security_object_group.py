from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelForm,
)
from utilities.forms.fields import (
    TagFilterField,
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
)
from utilities.forms.rendering import FieldSet

from netbox_nsm.models import SecurityObjectGroup, SecurityArea
from netbox_nsm.forms.widgets import ColorSelectTextWidget

__all__ = (
    "SecurityObjectGroupForm",
    "SecurityObjectGroupFilterForm",
    "SecurityObjectGroupBulkEditForm",
)


class SecurityObjectGroupForm(PrimaryModelForm):
    areas = DynamicModelMultipleChoiceField(
        queryset=SecurityArea.objects.all(),
        label=_("Areas"),
    )
    sub_groups = DynamicModelMultipleChoiceField(
        queryset=SecurityObjectGroup.objects.all(),
        required=False,
        label=_("Sub-Groups"),
    )

    color = forms.CharField(
        max_length=7,
        required=False,
        label=_('Color'),
        widget=ColorSelectTextWidget(),
        help_text=_('HTML color code (e.g. #aabbcc) used for this group in the policy view.'),
    )
    fieldsets = (
        FieldSet("name", "areas", "color", "description", name=_("Group")),
        FieldSet("sub_groups", name=_("Members")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = SecurityObjectGroup
        fields = (
            "name",
            "areas",
            "color",
            "sub_groups",
            "description",
            "comments",
            "tags",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        area_ids = set()
        if self.is_bound:
            area_ids.update(self.data.getlist("areas"))
        else:
            initial_areas = self.initial.get("areas") or []
            area_ids.update(
                getattr(area, "pk", area) for area in initial_areas if area
            )

        if not area_ids and self.instance.pk:
            area_ids.update(self.instance.areas.values_list("pk", flat=True))

        area_ids = {int(area_id) for area_id in area_ids if str(area_id).isdigit()}
        if not area_ids:
            return

        self.fields["sub_groups"].queryset = (
            SecurityObjectGroup.objects.filter(areas__pk__in=area_ids).distinct()
        )

    def clean_sub_groups(self):
        sub_groups = self.cleaned_data.get("sub_groups", [])
        if self.instance.pk and any(g.pk == self.instance.pk for g in sub_groups):
            raise forms.ValidationError(_("A group cannot be a sub-group of itself."))
        return sub_groups

    def clean(self):
        super().clean()
        areas = self.cleaned_data.get("areas")
        sub_groups = self.cleaned_data.get("sub_groups")
        area_ids = {a.pk for a in (areas or [])}

        if area_ids and sub_groups:
            bad = [
                g.name
                for g in sub_groups
                if not g.areas.filter(pk__in=area_ids).exists()
            ]
            if bad:
                raise forms.ValidationError(
                    _("These sub-groups do not match the selected group areas: %s")
                    % (", ".join(bad))
                )
        return self.cleaned_data


class SecurityObjectGroupFilterForm(PrimaryModelFilterSetForm):
    model = SecurityObjectGroup
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("area_id", name=_("Group")),
    )
    area_id = DynamicModelMultipleChoiceField(
        queryset=SecurityArea.objects.all(),
        required=False,
        label=_("Areas"),
    )
    tags = TagFilterField(model)


class SecurityObjectGroupBulkEditForm(PrimaryModelBulkEditForm):
    model = SecurityObjectGroup
    description = forms.CharField(max_length=200, required=False)
    color = forms.CharField(
        max_length=7,
        required=False,
        label=_('Color'),
        widget=ColorSelectTextWidget(),
        help_text=_('HTML color code (e.g. #aabbcc).'),
    )
    nullable_fields = ["description", "color"]
    fieldsets = (
        FieldSet("color", "description"),
        FieldSet("tags", name=_("Tags")),
    )
