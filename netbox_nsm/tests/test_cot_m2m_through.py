"""Tests for M2M through-table compatibility helpers."""

from unittest.mock import MagicMock, patch

from netbox_nsm.core.cot_m2m_through import (
    field_uses_polymorphic_through,
    read_m2m_ref_pairs,
    through_uses_polymorphic_columns,
)
from utilities.testing import TestCase


class CotM2MThroughTests(TestCase):
    def test_through_uses_polymorphic_columns_inspects_db_not_orm(self):
        through = MagicMock()
        through._meta.db_table = "custom_objects_3_group"
        with patch(
            "netbox_nsm.core.cot_m2m_through.through_table_column_names",
            return_value=frozenset({"id", "source_id", "target_id"}),
        ):
            self.assertFalse(through_uses_polymorphic_columns(through))

        with patch(
            "netbox_nsm.core.cot_m2m_through.through_table_column_names",
            return_value=frozenset({"id", "source_id", "content_type_id", "object_id"}),
        ):
            self.assertTrue(through_uses_polymorphic_columns(through))

    def test_field_uses_polymorphic_through_requires_metadata_and_db(self):
        field = MagicMock(is_polymorphic=True, through_model_name="Through_x")
        through = MagicMock()
        through._meta.db_table = "custom_objects_3_group"
        with patch(
            "netbox_nsm.core.cot_m2m_through.get_field_through_model",
            return_value=through,
        ):
            with patch(
                "netbox_nsm.core.cot_m2m_through.through_uses_polymorphic_columns",
                return_value=False,
            ):
                self.assertFalse(field_uses_polymorphic_through(field))

    def test_read_m2m_ref_pairs_from_standard_through(self):
        target_a = MagicMock(pk=3)
        target_b = MagicMock(pk=4)
        row_a = MagicMock(target=target_a)
        row_b = MagicMock(target=target_b)
        qs = MagicMock()
        qs.select_related.return_value = [row_a, row_b]
        through = MagicMock()
        through.objects.filter.return_value = qs
        with patch(
            "netbox_nsm.core.cot_m2m_through.through_uses_polymorphic_columns",
            return_value=False,
        ):
            with patch(
                "django.contrib.contenttypes.models.ContentType.objects.get_for_model",
                side_effect=[MagicMock(pk=272), MagicMock(pk=272)],
            ):
                self.assertEqual(read_m2m_ref_pairs(through, 1), [(272, 3), (272, 4)])


class BundleThroughMismatchIntegrationTests(TestCase):
    def test_diff_seed_objects_tolerates_polymorphic_flag_on_standard_through(self):
        from netbox_custom_objects.models import CustomObjectType

        from netbox_nsm.bundles.bundle_extensions import diff_seed_objects
        from netbox_nsm.bundles.dispatch import load_bundle
        from netbox_nsm.bundles.paths import bundle_json_path

        cot = CustomObjectType.objects.filter(slug="nsm_service_group").first()
        if cot is None:
            self.skipTest("nsm_service_group not deployed")
        field = cot.fields.filter(name="group").first()
        if field is None:
            self.skipTest("group field missing")

        orig = field.is_polymorphic
        field.is_polymorphic = True
        field.save(update_fields=["is_polymorphic"])
        self.addCleanup(lambda: field.__class__.objects.filter(pk=field.pk).update(is_polymorphic=orig))

        bundle = load_bundle(bundle_json_path("nsm_schema"))
        try:
            diff_seed_objects(bundle.get("objects"))
        except Exception as exc:
            self.fail(f"diff_seed_objects raised unexpectedly: {exc}")
