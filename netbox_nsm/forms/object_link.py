from django import forms
from django.utils.translation import gettext_lazy as _

from netbox_nsm.link_propagation import propagation_choices_for_object
from netbox_nsm.models import TypeConfig
from netbox_nsm.models.object_link import LinkPropagationChoices

__all__ = ("ObjectLinkAssignForm", "ObjectLinkEditForm")


class ObjectLinkPropagationForm(forms.Form):
    """Base form with propagation fields (must subclass forms.Form for Django 4.6+)."""

    propagation = forms.ChoiceField(
        label=_("Link type"),
        choices=LinkPropagationChoices.choices,
        initial=LinkPropagationChoices.DIRECT,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_propagation"}),
    )
    propagate_stop_on_own = forms.BooleanField(
        label=_("Stop when child has own link of same type"),
        required=False,
        initial=False,
        widget=forms.CheckboxInput(
            attrs={"class": "form-check-input", "id": "id_propagate_stop_on_own"}
        ),
    )

    def _configure_propagation_fields(self, source_object):
        self.source_object = source_object
        if source_object is not None:
            self.fields["propagation"].choices = propagation_choices_for_object(
                source_object
            )
        if self.fields["propagation"].choices == [
            (LinkPropagationChoices.DIRECT, LinkPropagationChoices.DIRECT.label)
        ]:
            self.fields["propagate_stop_on_own"].widget = forms.HiddenInput()

    def _clean_propagation_fields(self, data):
        propagation = data.get("propagation") or LinkPropagationChoices.DIRECT
        if getattr(self, "source_object", None) is not None:
            allowed_modes = {
                value
                for value, _label in propagation_choices_for_object(self.source_object)
            }
            if propagation not in allowed_modes:
                self.add_error("propagation", _("Invalid link type for this object."))
        if propagation == LinkPropagationChoices.DIRECT:
            data["propagate_stop_on_own"] = False
        return data


def _build_type_choices():
    """NSM types assignable as Object B in the Security Panel assign picker."""
    configs = list(
        TypeConfig.queryset_panel_linkable()
        .select_related("content_type")
        .order_by("name", "matching_class")
    )

    choices = [("", _("── Select type ──"))]
    for cfg in configs:
        if cfg.name and cfg.matching_class:
            label = f"{cfg.name} ({cfg.matching_class})"
        elif cfg.name:
            label = cfg.name
        else:
            ct = cfg.content_type
            model_class = ct.model_class()
            if model_class:
                label = (
                    f"{model_class._meta.app_config.verbose_name} → "
                    f"{str(model_class._meta.verbose_name).title()}"
                )
            else:
                label = f"{ct.app_label} → {ct.model}"
        choices.append((cfg.content_type.pk, label))
    return choices


class ObjectLinkAssignForm(ObjectLinkPropagationForm):
    """
    Form shown when the user clicks "Assign" in the Security panel.

    object_a_type / object_a_id are pre-filled from query-string params
    and rendered as hidden inputs.
    """

    object_a_type_id = forms.IntegerField(widget=forms.HiddenInput())
    object_a_id = forms.IntegerField(widget=forms.HiddenInput())

    object_b_type = forms.ChoiceField(
        label=_("Type (Object B)"),
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
        self.fields["object_b_type"].choices = _build_type_choices()
        self._configure_propagation_fields(source_object)

    def clean(self):
        data = super().clean()
        ct_pk = data.get("object_b_type")
        if not ct_pk:
            self.add_error("object_b_type", _("Please select a type."))
            return data

        if not TypeConfig.objects.filter(
            content_type_id=int(ct_pk),
            panel_linkable=True,
        ).exists():
            self.add_error(
                "object_b_type",
                _("This type is not linkable from the Security Panel."),
            )

        return self._clean_propagation_fields(data)


class ObjectLinkEditForm(ObjectLinkPropagationForm):
    """Edit propagation and comment on an existing ObjectLink."""

    comment = forms.CharField(
        label=_("Comment"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
    )

    def __init__(self, *args, source_object=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._configure_propagation_fields(source_object)

    def clean(self):
        data = super().clean()
        return self._clean_propagation_fields(data)
