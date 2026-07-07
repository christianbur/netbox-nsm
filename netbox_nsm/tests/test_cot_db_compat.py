"""Tests for netbox-custom-objects DB column compatibility."""

from django.db import connection

from netbox_nsm.bundles.cot_db_compat import ensure_cot_extension_column_defaults
from netbox_nsm.rulebooks.create import create_cot_rulebook_from_schema_yaml
from utilities.testing import TestCase

_MINIMAL_RULEBOOK_SCHEMA_JSON = """{
  "schema_version": "1",
  "types": [
    {
      "name": "nsm_rb_db_compat_test",
      "slug": "nsm_rb_db_compat_test",
      "verbose_name": "DB Compat Test",
      "verbose_name_plural": "DB Compat Test",
      "description": "Compat test rulebook",
      "group_name": "NSM Rulebooks",
      "fields": [
        {
          "id": 1,
          "name": "index",
          "type": "integer",
          "label": "Index",
          "required": true,
          "primary": true,
          "weight": 10
        }
      ],
      "removed_fields": []
    }
  ]
}"""


class CotDbCompatTests(TestCase):
    def test_ensure_cot_extension_column_defaults_is_idempotent(self):
        ensure_cot_extension_column_defaults()
        ensure_cot_extension_column_defaults()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, column_default
                FROM information_schema.columns
                WHERE table_name = 'netbox_custom_objects_customobjecttype'
                  AND column_name = 'menu_name'
                """
            )
            row = cursor.fetchone()
        if row is None:
            self.skipTest("menu_name column not present")
        self.assertIsNotNone(row[1])

    def test_create_rulebook_from_schema_json_succeeds(self):
        ensure_cot_extension_column_defaults()
        cot = create_cot_rulebook_from_schema_yaml(
            schema_yaml=_MINIMAL_RULEBOOK_SCHEMA_JSON,
            name="db_compat_test",
            verbose_name="DB Compat Test",
        )
        self.addCleanup(lambda: cot.delete())
        self.assertEqual(cot.slug, "nsm_rb_db_compat_test")
