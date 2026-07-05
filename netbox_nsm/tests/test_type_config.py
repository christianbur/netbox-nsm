"""Smoke tests for the ``type_metadata`` package (Phase 3 refactor)."""

from utilities.testing import TestCase


class TypeMetadataPackageImportTests(TestCase):
    """Verify that the new ``type_metadata`` package is importable and exposes
    all expected public symbols."""

    def test_config_module_importable(self):
        from netbox_nsm.type_metadata.config import (  # noqa: F401
            NsmTypeConfig,
            build_nsm_config_lookup,
            config_dict_from_spec,
            has_nsm_config_in_comments,
            normalize_nsm_config_list,
            parse_nsm_config_from_cot,
            resolve_nsm_config_for_cot,
        )

    def test_specs_module_importable(self):
        from netbox_nsm.type_metadata.specs import (  # noqa: F401
            REQUIRED_COT_SLUGS,
            TYPECONFIG_SPEC_BY_SLUG,
            TYPECONFIG_SPECS,
            TYPECONFIG_UI_SPECS,
        )

    def test_export_module_importable(self):
        from netbox_nsm.type_metadata.export import (  # noqa: F401
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

    def test_legacy_objects_stubs_forward_to_type_metadata(self):
        from netbox_nsm.objects import nsm_config, type_config_specs, type_config_export
        from netbox_nsm.type_metadata import config, specs, export

        self.assertIs(nsm_config.NsmTypeConfig, config.NsmTypeConfig)
        self.assertIs(type_config_specs.TYPECONFIG_SPEC_BY_SLUG, specs.TYPECONFIG_SPEC_BY_SLUG)
        self.assertIs(
            type_config_export.export_type_config_yaml, export.export_type_config_yaml
        )

    def test_legacy_views_stub_forwards_to_type_metadata(self):
        from netbox_nsm.views import type_metadata as old_views
        from netbox_nsm.type_metadata import views

        self.assertIs(old_views.TypeMetadataListView, views.TypeMetadataListView)

    def test_legacy_forms_stub_forwards_to_type_metadata(self):
        from netbox_nsm.forms import type_config as old_forms
        from netbox_nsm.type_metadata import forms

        self.assertIs(old_forms.NsmConfigForm, forms.NsmConfigForm)

    def test_specs_have_required_cot_slugs(self):
        from netbox_nsm.type_metadata.specs import REQUIRED_COT_SLUGS, TYPECONFIG_SPEC_BY_SLUG

        for slug in REQUIRED_COT_SLUGS:
            if slug != "nsm_object_link":
                self.assertIn(slug, TYPECONFIG_SPEC_BY_SLUG)

    def test_permissions_return_strings(self):
        from netbox_nsm.type_metadata.permissions import (
            nsm_config_view_permission,
            nsm_config_change_permission,
        )

        self.assertIsInstance(nsm_config_view_permission(), str)
        self.assertIsInstance(nsm_config_change_permission(), str)
