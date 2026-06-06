"""Tests for TypeConfig settings UI (form / table)."""

from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext as _

from ipam.models import Prefix

from netbox_nsm.forms.type_config import TypeConfigAddForm, TypeConfigForm
from netbox_nsm.models import TypeConfig
from netbox_nsm.tables.type_config import TypeConfigTable
from utilities.testing import TestCase


class TypeConfigFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)
        cls.type_config = TypeConfig.objects.create(
            name="Test Zones",
            content_type=cls.prefix_ct,
            matching_class="zone",
            inherit_links=True,
            inherit_stop_on_own=True,
        )

    def test_edit_form_excludes_inheritance_fields(self):
        form = TypeConfigForm(instance=self.type_config)
        self.assertNotIn("inherit_links", form.fields)
        self.assertNotIn("inherit_stop_on_own", form.fields)

    def test_edit_form_has_no_inheritance_fieldset(self):
        fieldset_names = [fs.name for fs in TypeConfigForm.fieldsets]
        self.assertNotIn(_("Inheritance"), fieldset_names)

    def test_add_form_excludes_inheritance_fields(self):
        form = TypeConfigAddForm()
        self.assertNotIn("inherit_links", form.fields)
        self.assertNotIn("inherit_stop_on_own", form.fields)

    def test_edit_save_preserves_legacy_inheritance_db_values(self):
        form = TypeConfigForm(
            instance=self.type_config,
            data={
                "name": "Renamed Zones",
                "matching_class": "zone",
                "display_template": "{name}",
                "panel_slugs": ["source"],
                "order_id": 10,
                "panel_linkable_types": [],
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        saved.refresh_from_db()
        self.assertEqual(saved.name, "Renamed Zones")
        self.assertTrue(saved.inherit_links)
        self.assertTrue(saved.inherit_stop_on_own)

    def test_table_default_columns_exclude_inheritance(self):
        columns = TypeConfigTable.Meta.default_columns
        self.assertNotIn("inherit_links", columns)
        self.assertNotIn("inherit_stop_on_own", columns)
