from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelForm,
)
from utilities.forms.fields import TagFilterField
from utilities.forms.rendering import FieldSet

from netbox_nsm.models import ObjectComment

__all__ = (
    "ObjectCommentForm",
    "ObjectCommentFilterForm",
    "ObjectCommentBulkEditForm",
)


class ObjectCommentForm(PrimaryModelForm):
    description = forms.CharField(max_length=200, required=False)
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 10}),
        label=_("Comment"),
        help_text=_("Supports Markdown formatting"),
    )

    fieldsets = (
        FieldSet("name", "description", name=_("Comment Object")),
        FieldSet("comment", name=_("Content")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = ObjectComment
        fields = ("name", "description", "comment", "comments", "tags")


class ObjectCommentFilterForm(PrimaryModelFilterSetForm):
    model = ObjectComment
    tag = TagFilterField(model)

    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
    )


class ObjectCommentBulkEditForm(PrimaryModelBulkEditForm):
    model = ObjectComment
    nullable_fields = ("description", "comment")
