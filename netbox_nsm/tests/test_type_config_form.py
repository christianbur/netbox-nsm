"""Tests for Object Config form (nsm_config)."""

from django.utils.translation import gettext as _

from netbox_nsm.type_metadata.forms import NsmAddressConfigForm, NsmConfigForm, area_labels_for_values
from netbox_nsm.forms.widgets import BtnCheckMultipleWidget
from netbox_nsm.type_metadata.specs import (
    TYPECONFIG_SORT_ORDER_BY_SLUG,
    TYPECONFIG_SPECS,
    TYPECONFIG_UI_SPECS,
    default_sort_order_for_slug,
)
from utilities.testing import TestCase


def _base_form_data(**overrides):
    data = {
        "role": "zone",
        "sort_order": 12,
        "display_template": "{{ name }}",
    }
    data.update(overrides)
    return data


class NsmConfigFormTests(TestCase):
    def test_form_has_rule_view_fields(self):
        form = NsmConfigForm()
        self.assertIn("sort_order", form.fields)
        self.assertIn("display_template", form.fields)
        self.assertIn("areas", form.fields)
        self.assertIsInstance(form.fields["areas"].widget, BtnCheckMultipleWidget)
        self.assertNotIn("linkable", form.fields)
        self.assertNotIn("inherit_links", form.fields)
        self.assertNotIn("linkable_types", form.fields)

    def test_areas_widget_renders_btn_check_group(self):
        form = NsmConfigForm(initial={"areas": ["action"]})
        html = form["areas"].as_widget()
        self.assertIn("nsm-btn-check-group", html)
        self.assertIn("btn-check", html)
        self.assertIn("Source / Destination", html)
        self.assertIn('value="action"', html)

    def test_form_has_rule_view_fieldsets(self):
        fieldset_names = [fs.name for fs in NsmConfigForm.fieldsets]
        self.assertIn(_("Metadata"), fieldset_names)
        self.assertIn(_("Rule View"), fieldset_names)
        self.assertNotIn(_("Security Links"), fieldset_names)
        self.assertIn("role", NsmConfigForm().fields)

    def test_to_config_dict_round_trip(self):
        form = NsmConfigForm(data=_base_form_data(role="zone", areas=["srcdst", "services"]))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.to_config_dict(),
            {
                "role": "zone",
                "sort_order": 12,
                "display_template": "{{ name }}",
                "areas": ["srcdst", "services"],
            },
        )

    def test_initial_from_config_dict_includes_areas(self):
        initial = NsmConfigForm.initial_from_config_dict(
            {
                "role": "zone",
                "sort_order": 5,
                "display_template": "{{ name | upper }}",
                "areas": ["action"],
            }
        )
        self.assertEqual(initial["areas"], ["action"])
        self.assertNotIn("linkable", initial)

    def test_area_labels_for_values(self):
        self.assertEqual(
            area_labels_for_values(["action", "services"]),
            ["Action", "Services"],
        )

    def test_ui_specs_include_object_link(self):
        ui_slugs = {spec["slug"] for spec in TYPECONFIG_UI_SPECS}
        spec_slugs = {spec["slug"] for spec in TYPECONFIG_SPECS}
        self.assertEqual(ui_slugs, spec_slugs)
        self.assertIn("nsm_object_link", ui_slugs)
        for slug, expected in {
            **TYPECONFIG_SORT_ORDER_BY_SLUG,
        }.items():
            self.assertEqual(default_sort_order_for_slug(slug), expected)

        form = NsmAddressConfigForm()
        fieldset_names = [fs.name for fs in form.fieldsets]
        self.assertIn(_("Rule View"), fieldset_names)
        self.assertNotIn(_("Security Links"), fieldset_names)
