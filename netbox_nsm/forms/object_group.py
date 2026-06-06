from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelForm,
)
from utilities.forms.fields import (
    TagFilterField,
    DynamicModelMultipleChoiceField,
)
from utilities.forms.rendering import FieldSet

from netbox_nsm.models import ObjectGroup
from netbox_nsm.forms.widgets import ColorSelectTextWidget
from netbox_nsm.panel_sections import get_panel_section_choices

__all__ = (
    "ObjectGroupForm",
    "ObjectGroupFilterForm",
    "ObjectGroupBulkEditForm",
)


class ObjectGroupForm(PrimaryModelForm):
    field_slugs = forms.MultipleChoiceField(
        choices=get_panel_section_choices,
        required=False,
        label=_("Field slugs"),
        widget=forms.CheckboxSelectMultiple,
    )
    sub_groups = DynamicModelMultipleChoiceField(
        queryset=ObjectGroup.objects.all(),
        required=False,
        label=_("Sub-Groups"),
    )

    color = forms.CharField(
        max_length=7,
        required=False,
        label=_("Color"),
        widget=ColorSelectTextWidget(),
        help_text=_(
            "HTML color code (e.g. #aabbcc) used for this group in the policy view."
        ),
    )
    fieldsets = (
        FieldSet("name", "field_slugs", "color", "description", name=_("Group")),
        FieldSet("sub_groups", name=_("Members")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = ObjectGroup
        fields = (
            "name",
            "field_slugs",
            "color",
            "sub_groups",
            "description",
            "comments",
            "tags",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.field_slugs:
            self.initial.setdefault("field_slugs", self.instance.field_slugs)

        field_slugs = set()
        if self.is_bound:
            field_slugs.update(self.data.getlist("field_slugs"))
        else:
            field_slugs.update(self.initial.get("field_slugs") or [])

        if not field_slugs and self.instance.pk:
            field_slugs.update(self.instance.field_slugs or [])

        if not field_slugs:
            return

        q = Q()
        for slug in field_slugs:
            q |= Q(field_slugs__contains=[slug])
        self.fields["sub_groups"].queryset = ObjectGroup.objects.filter(q).distinct()

    def clean_sub_groups(self):
        sub_groups = self.cleaned_data.get("sub_groups", [])
        if self.instance.pk and any(g.pk == self.instance.pk for g in sub_groups):
            raise forms.ValidationError(_("A group cannot be a sub-group of itself."))
        return sub_groups

    def clean(self):
        super().clean()
        field_slugs = set(self.cleaned_data.get("field_slugs") or [])
        sub_groups = self.cleaned_data.get("sub_groups")

        if field_slugs and sub_groups:
            bad = [
                g.name
                for g in sub_groups
                if not field_slugs.intersection(g.field_slugs or [])
            ]
            if bad:
                raise forms.ValidationError(
                    _("These sub-groups do not match the selected field slugs: %s")
                    % (", ".join(bad))
                )
        return self.cleaned_data


class ObjectGroupFilterForm(PrimaryModelFilterSetForm):
    model = ObjectGroup
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("field_slug", name=_("Group")),
    )
    field_slug = forms.MultipleChoiceField(
        choices=get_panel_section_choices,
        required=False,
        label=_("Field slugs"),
    )
    tags = TagFilterField(model)


class ObjectGroupBulkEditForm(PrimaryModelBulkEditForm):
    model = ObjectGroup
    description = forms.CharField(max_length=200, required=False)
    color = forms.CharField(
        max_length=7,
        required=False,
        label=_("Color"),
        widget=ColorSelectTextWidget(),
        help_text=_("HTML color code (e.g. #aabbcc)."),
    )
    nullable_fields = ["description", "color"]
    fieldsets = (
        FieldSet("color", "description"),
        FieldSet("tags", name=_("Tags")),
    )
