"""Tests for COT rulebook metadata (display name, description)."""

from types import SimpleNamespace
from unittest.mock import patch

from django.urls import reverse

from netbox_nsm.tests.rulebook_permission_helpers import grant_rulebook_cot_perms
from utilities.testing import TestCase

from netbox_nsm.objects.rulebook_config import (
    parse_rulebook_config_from_comments,
    resolve_rulebook_config_for_cot,
    save_rulebook_config_for_cot,
)
from netbox_nsm.rulebooks.create import (
    format_rulebook_display_name,
    normalize_rulebook_display_name,
    update_cot_rulebook_metadata,
)
from netbox_nsm.rulebooks.forms.cot import (
    CotRulebookCreateForm,
    CotRulebookDetailForm,
    CotRulebookMetadataForm,
)
from netbox_nsm.rulebooks.templates import (
    default_rulebook_schema_yaml,
    substitute_rulebook_schema_placeholders,
    RULEBOOK_GROUP,
)


class CotRulebookMetadataFormTests(TestCase):
    def test_metadata_form_prefills_cot_values(self):
        cot = SimpleNamespace(
            verbose_name="My Rulebook",
            name="nsm_rb_my_rulebook",
            description="Existing text",
        )
        form = CotRulebookMetadataForm(cot=cot)
        self.assertEqual(form.initial["verbose_name"], "My Rulebook")
        self.assertEqual(form.initial["description"], "Existing text")

    def test_create_form_has_description_field(self):
        with patch(
            "netbox_nsm.rulebooks.forms.cot.deployed_rulebook_parent_choices",
            return_value=[("", "—")],
        ):
            form = CotRulebookCreateForm()
        self.assertIn("description", form.fields)

    def test_create_form_requires_name(self):
        with patch(
            "netbox_nsm.rulebooks.forms.cot.deployed_rulebook_parent_choices",
            return_value=[("", "—")],
        ):
            form = CotRulebookCreateForm(
                data={
                    "schema_yaml": default_rulebook_schema_yaml(),
                    "name": "",
                    "verbose_name": "",
                    "description": "",
                    "parent_slug": "",
                }
            )
        self.assertFalse(form.is_valid())
        self.assertIn("verbose_name", form.errors)
        self.assertIn("name", form.errors)

    def test_create_form_locks_metadata_from_literal_schema_yaml(self):
        schema_yaml = substitute_rulebook_schema_placeholders(
            default_rulebook_schema_yaml(),
            display_name="Bench Addresses",
            name="bench_addresses",
            description="Copied schema",
        )
        with patch(
            "netbox_nsm.rulebooks.forms.cot.deployed_rulebook_parent_choices",
            return_value=[("", "—")],
        ):
            form = CotRulebookCreateForm(
                data={
                    "schema_yaml": schema_yaml,
                    "name": "tampered",
                    "verbose_name": "Tampered",
                    "description": "Tampered",
                    "parent_slug": "",
                }
            )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["name"], "bench_addresses")
        self.assertEqual(
            form.cleaned_data["verbose_name"],
            format_rulebook_display_name("Bench Addresses"),
        )
        self.assertEqual(form.cleaned_data["description"], "Copied schema")
        self.assertEqual(
            form.fields["name"].widget.attrs.get("readonly"),
            "readonly",
        )
        self.assertEqual(
            form.fields["verbose_name"].widget.attrs.get("readonly"),
            "readonly",
        )

    def test_create_form_keeps_fields_editable_with_placeholder_schema(self):
        with patch(
            "netbox_nsm.rulebooks.forms.cot.deployed_rulebook_parent_choices",
            return_value=[("", "—")],
        ):
            form = CotRulebookCreateForm()
        self.assertNotIn("readonly", form.fields["name"].widget.attrs)
        self.assertNotIn("readonly", form.fields["verbose_name"].widget.attrs)
        self.assertEqual(form.schema_metadata_locked, {})

    def test_create_form_derives_name_from_display_name(self):
        with patch(
            "netbox_nsm.rulebooks.forms.cot.deployed_rulebook_parent_choices",
            return_value=[("", "—")],
        ):
            form = CotRulebookCreateForm(
                data={
                    "schema_yaml": default_rulebook_schema_yaml(),
                    "name": "",
                    "verbose_name": "Test 01",
                    "description": "",
                    "parent_slug": "",
                }
            )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["name"], "test_01")
        self.assertEqual(
            form.cleaned_data["verbose_name"],
            format_rulebook_display_name("Test 01"),
        )


class CotRulebookMetadataViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from netbox_custom_objects.models import CustomObjectType

        cls.cot = CustomObjectType.objects.create(
            name="nsm_rb_meta_test",
            slug="nsm_rb_meta_test",
            verbose_name="Meta Test",
            description="Original description",
            group_name=RULEBOOK_GROUP,
        )

    def test_detail_readonly_without_edit_query(self):
        grant_rulebook_cot_perms(self, self.cot, view=True, change=True)
        url = reverse(
            "plugins:netbox_nsm:cot_rulebook",
            kwargs={"slug": self.cot.slug},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Original description")
        self.assertContains(response, "?edit=1")
        self.assertNotContains(response, 'name="verbose_name"')

    def test_detail_edit_mode_shows_inline_form(self):
        grant_rulebook_cot_perms(self, self.cot, view=True, change=True)
        url = reverse(
            "plugins:netbox_nsm:cot_rulebook",
            kwargs={"slug": self.cot.slug},
        )
        response = self.client.get(f"{url}?edit=1")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="verbose_name"')
        self.assertContains(response, 'name="description"')
        self.assertContains(response, 'name="parent_slug"')

    def test_post_detail_form_updates_cot(self):
        grant_rulebook_cot_perms(self, self.cot, view=True, change=True)
        url = reverse(
            "plugins:netbox_nsm:cot_rulebook",
            kwargs={"slug": self.cot.slug},
        )
        response = self.client.post(
            url,
            {
                "verbose_name": "Test 01",
                "description": "Updated description",
                "parent_slug": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.cot.refresh_from_db()
        expected = format_rulebook_display_name("Test 01")
        self.assertEqual(self.cot.verbose_name, expected)
        self.assertEqual(self.cot.verbose_name_plural, expected)
        self.assertEqual(self.cot.description, "Updated description")

    def test_post_detail_form_keeps_existing_rulebook_prefix(self):
        grant_rulebook_cot_perms(self, self.cot, view=True, change=True)
        url = reverse(
            "plugins:netbox_nsm:cot_rulebook",
            kwargs={"slug": self.cot.slug},
        )
        response = self.client.post(
            url,
            {
                "verbose_name": "Rulebook Custom Label",
                "description": "",
                "parent_slug": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.cot.refresh_from_db()
        self.assertEqual(self.cot.verbose_name, "Rulebook Custom Label")
        self.assertEqual(self.cot.verbose_name_plural, "Rulebook Custom Label")

    def test_post_detail_form_updates_list_name(self):
        grant_rulebook_cot_perms(self, self.cot, view=True, change=True)
        detail_url = reverse(
            "plugins:netbox_nsm:cot_rulebook",
            kwargs={"slug": self.cot.slug},
        )
        self.client.post(
            detail_url,
            {
                "verbose_name": "Test 01",
                "description": "",
                "parent_slug": "",
            },
        )
        list_url = reverse("plugins:netbox_nsm:rulebook_list")
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, format_rulebook_display_name("Test 01"))

    def test_detail_form_normalizes_bare_display_name(self):
        with patch(
            "netbox_nsm.rulebooks.forms.cot.deployed_rulebook_parent_choices",
            return_value=[("", "—")],
        ):
            form = CotRulebookDetailForm(
                cot=self.cot,
                rulebook_slug=self.cot.slug,
                data={
                    "verbose_name": "Test 01",
                    "description": "",
                    "parent_slug": "",
                },
            )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["verbose_name"],
            format_rulebook_display_name("Test 01"),
        )

    def test_detail_form_prefills_cot_values(self):
        form = CotRulebookDetailForm(cot=self.cot, rulebook_slug=self.cot.slug)
        self.assertEqual(form.initial["verbose_name"], "Meta Test")
        self.assertEqual(form.initial["description"], "Original description")

    def test_update_helper_persists_fields(self):
        update_cot_rulebook_metadata(
            self.cot.slug,
            verbose_name="Test 01",
            description="Helper description",
        )
        self.cot.refresh_from_db()
        expected = format_rulebook_display_name("Test 01")
        self.assertEqual(self.cot.verbose_name, expected)
        self.assertEqual(self.cot.verbose_name_plural, expected)
        self.assertEqual(self.cot.description, "Helper description")


class CotRulebookMatrixTabMetadataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from netbox_custom_objects.models import CustomObjectType

        cls.cot = CustomObjectType.objects.create(
            name="nsm_rb_matrix_test",
            slug="nsm_rb_matrix_test",
            verbose_name="Matrix Rulebook",
            description="",
            group_name=RULEBOOK_GROUP,
        )

    @patch(
        "netbox_nsm.matrix.cot_matrix_tab_context.cot_rulebook_matrix_capable",
        return_value=True,
    )
    def test_detail_form_includes_matrix_tab_field(self, _mock_capable):
        form = CotRulebookDetailForm(cot=self.cot, rulebook_slug=self.cot.slug)
        self.assertIn("matrix_tab_enabled", form.fields)
        self.assertTrue(form.initial["matrix_tab_enabled"])

    @patch(
        "netbox_nsm.rulebooks.virtual_cot.cot_rulebook_matrix_enabled",
        return_value=True,
    )
    @patch(
        "netbox_nsm.rulebooks.virtual_cot.cot_rulebook_matrix_capable",
        return_value=True,
    )
    def test_detail_readonly_shows_matrix_tab_row(
        self, _mock_capable, _mock_enabled
    ):
        grant_rulebook_cot_perms(self, self.cot, view=True)
        url = reverse(
            "plugins:netbox_nsm:cot_rulebook",
            kwargs={"slug": self.cot.slug},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Matrix tab")
        self.assertContains(response, "Show")

    @patch(
        "netbox_nsm.matrix.cot_matrix_tab_context.cot_rulebook_matrix_capable",
        return_value=True,
    )
    def test_post_detail_form_disables_matrix_tab(self, _mock_capable):
        grant_rulebook_cot_perms(self, self.cot, view=True, change=True)
        url = reverse(
            "plugins:netbox_nsm:cot_rulebook",
            kwargs={"slug": self.cot.slug},
        )
        response = self.client.post(
            url,
            {
                "verbose_name": "Matrix Rulebook",
                "description": "",
                "parent_slug": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.cot.refresh_from_db()
        config = parse_rulebook_config_from_comments(self.cot.comments or "")
        self.assertFalse(config["matrix_tab_enabled"])

    @patch(
        "netbox_nsm.matrix.cot_matrix_tab_context.cot_rulebook_matrix_capable",
        return_value=True,
    )
    def test_post_detail_form_keeps_matrix_tab_enabled(self, _mock_capable):
        grant_rulebook_cot_perms(self, self.cot, view=True, change=True)
        url = reverse(
            "plugins:netbox_nsm:cot_rulebook",
            kwargs={"slug": self.cot.slug},
        )
        response = self.client.post(
            url,
            {
                "verbose_name": "Matrix Rulebook",
                "description": "",
                "parent_slug": "",
                "matrix_tab_enabled": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.cot.refresh_from_db()
        config = parse_rulebook_config_from_comments(self.cot.comments or "")
        self.assertTrue(config["matrix_tab_enabled"])


class CotRulebookRowGroupSettingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from netbox_custom_objects.models import CustomObjectType

        cls.cot = CustomObjectType.objects.create(
            name="nsm_rb_rowgroup_test",
            slug="nsm_rb_rowgroup_test",
            verbose_name="Row Group Rulebook",
            description="",
            group_name=RULEBOOK_GROUP,
        )

    def test_detail_form_includes_row_group_field(self):
        form = CotRulebookDetailForm(cot=self.cot, rulebook_slug=self.cot.slug)
        self.assertIn("row_group_by_col_id", form.fields)
        self.assertEqual(form.initial["row_group_by_col_id"], "")

    def test_set_row_group_by_col_id_persists(self):
        save_rulebook_config_for_cot(self.cot, {"row_group_by_col_id": "name"})
        self.cot.refresh_from_db()
        config = resolve_rulebook_config_for_cot(self.cot)
        self.assertEqual(config["row_group_by_col_id"], "name")
        from netbox_nsm.rulebooks.cot_hierarchy import get_cot_row_group_by_col_id

        self.assertEqual(get_cot_row_group_by_col_id(self.cot.slug), "name")

    def test_row_group_by_col_id_includes_none_choice(self):
        form = CotRulebookDetailForm(cot=self.cot, rulebook_slug=self.cot.slug)
        self.assertEqual(form.fields["row_group_by_col_id"].choices[0], ("", "None"))

    def test_clear_row_group_by_col_id_persists(self):
        save_rulebook_config_for_cot(self.cot, {"row_group_by_col_id": "name"})
        save_rulebook_config_for_cot(self.cot, {"row_group_by_col_id": ""})
        self.cot.refresh_from_db()
        config = resolve_rulebook_config_for_cot(self.cot)
        self.assertEqual(config["row_group_by_col_id"], "")
        from netbox_nsm.rulebooks.cot_hierarchy import get_cot_row_group_by_col_id

        self.assertEqual(get_cot_row_group_by_col_id(self.cot.slug), "")
