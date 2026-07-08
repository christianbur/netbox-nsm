from django import forms
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _

from netbox_nsm.type_metadata.config import (
    filter_assignable_configs,
    is_assignable_from_content_type,
    iter_linkable_configs,
)

__all__ = ("ObjectLinkAssignForm", "ObjectLinkEditForm")


def _build_type_choices(source_content_type_id=None):
    """NSM types assignable as policy object in the Security Panel assign picker."""
    if source_content_type_id is not None:
        configs = filter_assignable_configs(int(source_content_type_id))
    else:
        configs = sorted(
            iter_linkable_configs(),
            key=lambda c: (c.name or "").lower(),
        )

    choices = [("", _("── Select type ──"))]
    for cfg in configs:
        if cfg.name:
            label = cfg.name
        else:
            ct = ContentType.objects.get(pk=cfg.content_type_id)
            model_class = ct.model_class()
            if model_class:
                label = (
                    f"{model_class._meta.app_config.verbose_name} → "
                    f"{str(model_class._meta.verbose_name).title()}"
                )
            else:
                label = f"{ct.app_label} → {ct.model}"
        choices.append((cfg.content_type_id, label))
    return choices


class ObjectLinkAssignForm(forms.Form):
    """
    Form shown when the user clicks "Assign" in the Security panel.

    object_a_type / object_a_id are pre-filled from query-string params
    and rendered as hidden inputs.
    """

    object_a_type_id = forms.IntegerField(widget=forms.HiddenInput())
    object_a_id = forms.IntegerField(widget=forms.HiddenInput())

    object_b_type = forms.ChoiceField(
        label=_("Type (Security object)"),
        choices=[],
    )
    object_b_id = forms.IntegerField(
        label=_("Element"),
        min_value=1,
        help_text=_(
            "ID of the object. Select a type first, then a dropdown will appear."
        ),
        widget=forms.HiddenInput(),
        required=False,
    )
    object_b_display = forms.CharField(
        label=_("Object"),
        required=False,
        widget=forms.Select(attrs={"id": "id_object_b_display"}),
    )

    comment = forms.CharField(
        label=_("Comment"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, source_object=None, **kwargs):
        super().__init__(*args, **kwargs)
        source_ct_id = self._resolve_source_content_type_id(
            source_object,
            data=self.data if self.is_bound else None,
            initial=self.initial,
        )
        self.fields["object_b_type"].choices = _build_type_choices(source_ct_id)

    @staticmethod
    def _resolve_source_content_type_id(source_object, data=None, initial=None):
        if source_object is not None:
            from django.contrib.contenttypes.models import ContentType

            return ContentType.objects.get_for_model(source_object).pk
        for source in (data or {}, initial or {}):
            raw = source.get("object_a_type_id")
            if raw not in (None, ""):
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    pass
        return None

    def clean(self):
        data = super().clean()
        ct_pk = data.get("object_b_type")
        if not ct_pk:
            self.add_error("object_b_type", _("Please select a type."))
            return data

        object_a_type_id = data.get("object_a_type_id")
        if object_a_type_id is None:
            self.add_error(
                "object_b_type",
                _("This type is not linkable from the Security Panel."),
            )
            return data

        if not is_assignable_from_content_type(int(object_a_type_id), int(ct_pk)):
            self.add_error(
                "object_b_type",
                _("This type is not linkable from the Security Panel."),
            )

        return data


class ObjectLinkEditForm(forms.Form):
    """Edit comment on an existing nsm_object_link row."""

    comment = forms.CharField(
        label=_("Comment"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
    )
