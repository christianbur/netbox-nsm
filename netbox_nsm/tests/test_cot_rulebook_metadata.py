"""Tests for COT rulebook metadata (display name, description)."""

from types import SimpleNamespace
from unittest.mock import patch

from django.urls import reverse

from utilities.testing import TestCase

from netbox_nsm.models import CotRulebook
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
from netbox_nsm.rulebooks.templates import RULEBOOK_GROUP


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

    def test_create_form_defaults_display_name(self):
        with patch(
            "netbox_nsm.rulebooks.forms.cot.deployed_rulebook_parent_choices",
            return_value=[("", "—")],
        ):
            form = CotRulebookCreateForm(
                data={
                    "template_slug": "nsm_rb_0001_template",
                    "name": "Test 01",
                    "verbose_name": "",
                    "description": "",
                    "parent_slug": "",
                }
            )
        self.assertTrue(form.is_valid(), form.errors)
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
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.add_rulebook")
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
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.add_rulebook")
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
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.add_rulebook")
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
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.add_rulebook")
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
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.add_rulebook")
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
        "netbox_nsm.rulebooks.virtual_cot.cot_rulebook_matrix_capable",
        return_value=True,
    )
    def test_detail_readonly_shows_matrix_tab_row(self, _mock_capable):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse(
            "plugins:netbox_nsm:cot_rulebook",
            kwargs={"slug": self.cot.slug},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Matrix tab")
        self.assertContains(response, "Show")

    @patch(
        "netbox_nsm.rulebooks.virtual_cot.cot_rulebook_matrix_capable",
        return_value=True,
    )
    def test_post_detail_form_disables_matrix_tab(self, _mock_capable):
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.add_rulebook")
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
        row = CotRulebook.objects.get(slug=self.cot.slug)
        self.assertFalse(row.matrix_tab_enabled)

    @patch(
        "netbox_nsm.rulebooks.virtual_cot.cot_rulebook_matrix_capable",
        return_value=True,
    )
    def test_post_detail_form_keeps_matrix_tab_enabled(self, _mock_capable):
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.add_rulebook")
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
        row = CotRulebook.objects.get(slug=self.cot.slug)
        self.assertTrue(row.matrix_tab_enabled)
