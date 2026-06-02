from django import forms
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _

from netbox_nsm.models import NSMObjectLink, TypeConfig

__all__ = ("NSMObjectLinkAssignForm",)


def _build_type_choices():
    """Return choices with human-readable app → model labels from TypeConfig."""
    all_configs = list(
        TypeConfig.objects.select_related("content_type").order_by(
            "content_type__app_label", "content_type__model", "matching_class"
        )
    )
    # Count entries per ContentType to decide when to add matching_class suffix
    ct_counts: dict[int, int] = {}
    for cfg in all_configs:
        ct_counts[cfg.content_type_id] = ct_counts.get(cfg.content_type_id, 0) + 1

    choices = [("", _("── Select type ──"))]
    for cfg in all_configs:
        ct = cfg.content_type
        model_class = ct.model_class()
        if model_class:
            app_name = model_class._meta.app_config.verbose_name
            model_name = str(model_class._meta.verbose_name).title()
        else:
            app_name = ct.app_label.replace("_", " ").title()
            model_name = ct.model.replace("_", " ").title()
        label = f"{app_name} → {model_name}"
        if ct_counts[cfg.content_type_id] > 1 and cfg.matching_class:
            label += f" ({cfg.get_matching_class_display()})"
        choices.append((ct.pk, label))
    return choices


class NSMObjectLinkAssignForm(forms.Form):
    """
    Form shown when the user clicks "Assign" in the Security panel.

    object_a_type / object_a_id are pre-filled from query-string params
    and rendered as hidden inputs.
    """

    object_a_type_id = forms.IntegerField(widget=forms.HiddenInput())
    object_a_id = forms.IntegerField(widget=forms.HiddenInput())

    object_b_type = forms.ChoiceField(
        label=_("Type (Object B)"),
        choices=[],  # populated in __init__
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
    # Populated via AJAX – rendered as a select
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["object_b_type"].choices = _build_type_choices()

    def clean(self):
        data = super().clean()
        ct_pk = data.get("object_b_type")
        obj_id = data.get("object_b_id")

        if not ct_pk:
            self.add_error("object_b_type", _("Please select a type."))
        if not obj_id:
            self.add_error("object_b_display", _("Please select an object."))
        return data
