"""Tests for Object Config form (nsm_config)."""

from netbox_nsm.forms.type_config import NsmAddressConfigForm, NsmConfigForm
from netbox_nsm.objects.type_config_specs import (
    TYPECONFIG_LIST_EXCLUDED_SLUGS,
    TYPECONFIG_SORT_ORDER_BY_SLUG,
    TYPECONFIG_UI_SPECS,
    default_sort_order_for_slug,
)
from utilities.testing import TestCase


class NsmConfigFormTests(TestCase):
    def test_form_has_rule_view_fields_only(self):
        form = NsmConfigForm()
        self.assertIn("sort_order", form.fields)
        self.assertIn("display_template", form.fields)
        self.assertNotIn("inherit_links", form.fields)
        self.assertNotIn("panel_linkable_types", form.fields)

    def test_form_has_rule_view_fieldset(self):
        from django.utils.translation import gettext as _

        fieldset_names = [fs.name for fs in NsmConfigForm.fieldsets]
        self.assertIn(_("Rule View"), fieldset_names)

    def test_to_config_dict_round_trip(self):
        form = NsmConfigForm(
            data={
                "sort_order": 12,
                "display_template": "{name}",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.to_config_dict(),
            {"sort_order": 12, "display_template": "{name}"},
        )

    def test_ui_specs_exclude_object_link_with_default_sort_orders(self):
        ui_slugs = {spec["slug"] for spec in TYPECONFIG_UI_SPECS}
        self.assertEqual(ui_slugs & TYPECONFIG_LIST_EXCLUDED_SLUGS, set())
        self.assertNotIn("nsm_object_link", ui_slugs)
        for slug, expected in TYPECONFIG_SORT_ORDER_BY_SLUG.items():
            self.assertEqual(default_sort_order_for_slug(slug), expected)

    def test_nsm_address_form_includes_object_builder_fieldset(self):
        from django.utils.translation import gettext as _

        form = NsmAddressConfigForm()
        fieldset_names = [fs.name for fs in form.fieldsets]
        self.assertIn(_("Rule View"), fieldset_names)
        self.assertIn(_("Object Sync"), fieldset_names)
        self.assertIn("template_ipaddress", form.fields)

    def test_nsm_address_form_round_trip_object_builder(self):
        form = NsmAddressConfigForm(
            data={
                "sort_order": 12,
                "display_template": "{name}",
                "object_builder_enabled": True,
                "template_ipaddress": "H-{host}",
                "copy_description_ipaddress": True,
                "template_prefix": "N-{network}-{prefix_length}",
                "template_iprange": "R-{start_address}-{end_address}",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        config = form.to_config_dict()
        self.assertTrue(config["object_builder"]["enabled"])
        self.assertEqual(
            config["object_builder"]["sources"]["ipam.ipaddress"]["build_template"],
            "H-{host}",
        )
