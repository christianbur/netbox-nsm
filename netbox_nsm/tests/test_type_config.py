"""Smoke tests for the ``type_metadata`` package (Phase 3 refactor)."""

from utilities.testing import TestCase


class TypeMetadataPackageImportTests(TestCase):
    """Verify that the new ``type_metadata`` package is importable and exposes
    all expected public symbols."""

    def test_config_module_importable(self):
        from netbox_nsm.type_metadata.config import (  # noqa: F401
            NsmTypeConfig,
            apply_schema_bundle_metadata,
            build_nsm_config_lookup,
            config_dict_from_metadata_block,
            has_nsm_config_in_comments,
            metadata_block_for_cot_slug,
            normalize_nsm_config_list,
            parse_nsm_config_from_cot,
            resolve_nsm_config_for_cot,
        )

    def test_specs_module_importable(self):
        from netbox_nsm.type_metadata.specs import (  # noqa: F401
            REQUIRED_COT_SLUGS,
            TYPECONFIG_LIST_EXCLUDED_SLUGS,
        )

    def test_export_module_importable(self):
        from netbox_nsm.type_metadata.export import (  # noqa: F401
            apply_schema_bundle_metadata,
            build_type_config_export_data,
            content_type_export_ref,
            export_all_type_configs_yaml,
            export_type_config_yaml,
            format_type_config_comment_yaml,
        )

    def test_permissions_module_importable(self):
        from netbox_nsm.type_metadata.permissions import (  # noqa: F401
            nsm_config_add_permission,
            nsm_config_change_permission,
            nsm_config_delete_permission,
            nsm_config_view_permission,
        )

    def test_rulebook_module_importable(self):
        from netbox_nsm.type_metadata.rulebook import (  # noqa: F401
            DEFAULT_RULEBOOK_CONFIG,
            normalize_rulebook_config,
            parse_rulebook_config_from_comments,
        )

    def test_views_module_importable(self):
        from netbox_nsm.type_metadata.views import (  # noqa: F401
            TypeMetadataAddView,
            TypeMetadataDeleteView,
            TypeMetadataEditView,
            TypeMetadataListView,
            TypeMetadataListEntry,
            TypeMetadataView,
        )

    def test_forms_module_importable(self):
        from netbox_nsm.type_metadata.forms import (  # noqa: F401
            NsmAddressConfigForm,
            NsmConfigForm,
            config_form_class_for_slug,
        )

    def test_bundle_metadata_has_required_cot_slugs(self):
        from netbox_nsm.type_metadata.config import metadata_block_for_cot_slug
        from netbox_nsm.type_metadata.specs import REQUIRED_COT_SLUGS

        for slug in REQUIRED_COT_SLUGS:
            if slug != "nsm_object_link":
                self.assertIsNotNone(
                    metadata_block_for_cot_slug(slug),
                    msg=f"missing bundle metadata for {slug}",
                )

    def test_permissions_return_strings(self):
        from netbox_nsm.type_metadata.permissions import (
            nsm_config_view_permission,
            nsm_config_change_permission,
        )

        self.assertIsInstance(nsm_config_view_permission(), str)
        self.assertIsInstance(nsm_config_change_permission(), str)
