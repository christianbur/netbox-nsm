"""Virtual all-rules rulebook list entry and dedicated page."""

from django.urls import reverse

from django.contrib.contenttypes.models import ContentType

from netbox_nsm.models import (
    Rule,
    Rulebook,
    RulebookField,
    RulebookFieldKind,
    RulebookTypeChoices,
)
from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields
from netbox_nsm.virtual_rulebook_detail import (
    VIRTUAL_ALL_RULES_FIELD_SLUG,
    load_virtual_all_rules_fields_for_detail,
)
from netbox_nsm.virtual_rulebook import (
    ALL_RULES_CHANGELOG_URL_NAME,
    ALL_RULES_CONTACTS_URL_NAME,
    ALL_RULES_JOURNAL_URL_NAME,
    ALL_RULES_RULEBOOK_URL_NAME,
    ALL_RULES_RULES_URL_NAME,
    VIRTUAL_ALL_RULES_PK,
    build_virtual_all_rules_row,
    is_virtual_all_rules_rulebook,
)
from utilities.testing import TestCase


class VirtualAllRulesRulebookTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rb = Rulebook.objects.create(
            name="Security Rules RB", rulebook_type=RulebookTypeChoices.SECURITY_RULES
        )
        ensure_system_rulebook_fields(cls.rb)
        cls.rule = Rule.objects.create(rulebook=cls.rb, name="r1", index=10)

    def test_virtual_rulebook_meta_delegates_to_rulebook_model(self):
        """Plugin panels resolve ContentType via _meta.model / _meta.concrete_model."""
        virtual = build_virtual_all_rules_row()
        self.assertIs(virtual._meta.concrete_model, Rulebook)
        self.assertIs(virtual._meta.model, Rulebook)
        self.assertEqual(virtual._meta.label_lower, "netbox_nsm.rulebook")
        ct = ContentType.objects.get_for_model(virtual)
        self.assertEqual(ct.model_class(), Rulebook)

    def test_virtual_row_helpers(self):
        virtual = build_virtual_all_rules_row()
        self.assertTrue(is_virtual_all_rules_rulebook(virtual))
        self.assertFalse(is_virtual_all_rules_rulebook(self.rb))
        self.assertEqual(virtual.pk, VIRTUAL_ALL_RULES_PK)
        self.assertEqual(str(virtual), "All Rules")
        self.assertEqual(virtual.name, "All Rules")
        self.assertEqual(virtual.rule_count, 1)
        overview_url = reverse(f"plugins:netbox_nsm:{ALL_RULES_RULEBOOK_URL_NAME}")
        rules_tab_url = reverse(f"plugins:netbox_nsm:{ALL_RULES_RULES_URL_NAME}")
        self.assertEqual(virtual.get_absolute_url(), overview_url)
        self.assertEqual(virtual.get_rules_tab_url(), rules_tab_url)
        self.assertIn(f"/rulebooks/{VIRTUAL_ALL_RULES_PK}/", overview_url)

    def test_list_excludes_virtual_all_rules_row(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        table = response.context["table"]
        names = [str(row.record.name) for row in table.rows]
        self.assertNotIn("All Rules", names)
        self.assertTrue(
            any(
                is_virtual_all_rules_rulebook(row.record) is False for row in table.rows
            )
        )

    def test_list_has_no_rules_all_tab(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        response = self.client.get(reverse("plugins:netbox_nsm:rulebook_list"))
        content = response.content.decode()
        self.assertNotIn('id="rules-all-tab"', content)
        self.assertNotIn("tab=rules-all", content)
        self.assertNotIn('id="rules-all-grid"', content)

    def test_virtual_rulebook_has_matrix_disabled(self):
        virtual = build_virtual_all_rules_row()
        self.assertFalse(virtual.matrix_tab_enabled)

    def test_all_rules_detail_page_has_rulebook_tabs(self):
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "tenancy.view_contactassignment",
            "extras.view_journalentry",
            "core.view_objectchange",
        )
        url = reverse(f"plugins:netbox_nsm:{ALL_RULES_RULEBOOK_URL_NAME}")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('class="nav nav-tabs"', content)
        self.assertIn(reverse("plugins:netbox_nsm:all_rules_rules"), content)
        self.assertIn(reverse("plugins:netbox_nsm:all_rules_contacts"), content)
        self.assertIn(reverse("plugins:netbox_nsm:all_rules_journal"), content)
        self.assertIn(reverse("plugins:netbox_nsm:all_rules_changelog"), content)
        self.assertNotIn("/rulebooks/0/matrix/", content)
        self.assertIn("Security Policy", content)
        self.assertIn("Fields", content)
        self.assertNotIn("Add Field", content)
        self.assertNotIn("alert-danger", content)
        self.assertNotIn("An error occurred when loading content from plugin", content)
        self.assertIn("All Rules", content)
        self.assertNotIn("VirtualAllRulesRulebook object at", content)

    def test_all_rules_rules_page_renders_rules_tab_layout(self):
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.view_rule")
        url = reverse(f"plugins:netbox_nsm:{ALL_RULES_RULES_URL_NAME}")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('class="nav nav-tabs"', content)
        self.assertIn(url, content)
        self.assertIn("nsm-rules-table-scroll", content)
        self.assertIn("Rulebook", content)
        self.assertIn(self.rb.name, content)
        self.assertIn("r1", content)
        self.assertNotIn("Add Rule", content)
        rule_list_url = reverse("plugins:netbox_nsm:rule_list")
        self.assertNotEqual(response.request["PATH_INFO"], rule_list_url)

    def test_all_rules_feature_tabs_render_readonly(self):
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "tenancy.view_contactassignment",
            "extras.view_journalentry",
            "core.view_objectchange",
        )
        for url_name in (
            ALL_RULES_CONTACTS_URL_NAME,
            ALL_RULES_JOURNAL_URL_NAME,
            ALL_RULES_CHANGELOG_URL_NAME,
        ):
            response = self.client.get(reverse(f"plugins:netbox_nsm:{url_name}"))
            self.assertEqual(response.status_code, 200, url_name)
            content = response.content.decode()
            self.assertIn('class="nav nav-tabs"', content)
            self.assertNotIn("Add a contact", content)
            self.assertNotIn("New Journal Entry", content)

    def test_list_does_not_link_virtual_all_rules_row(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        all_rules_url = reverse(f"plugins:netbox_nsm:{ALL_RULES_RULEBOOK_URL_NAME}")
        rules_url = reverse(f"plugins:netbox_nsm:{ALL_RULES_RULES_URL_NAME}")
        response = self.client.get(reverse("plugins:netbox_nsm:rulebook_list"))
        content = response.content.decode()
        self.assertNotIn(all_rules_url, content)
        self.assertNotIn(rules_url, content)
        self.assertNotIn(">All Rules<", content)

    def test_legacy_all_rules_urls_redirect_to_pk_zero(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        cases = (
            (
                "/plugins/netbox-nsm/rulebooks/all-rules/",
                reverse(f"plugins:netbox_nsm:{ALL_RULES_RULEBOOK_URL_NAME}"),
            ),
            (
                "/plugins/netbox-nsm/rulebooks/all-rules/rules/",
                reverse(f"plugins:netbox_nsm:{ALL_RULES_RULES_URL_NAME}"),
            ),
            (
                "/plugins/netbox-nsm/rulebooks/all-rules/matrix/",
                reverse(f"plugins:netbox_nsm:{ALL_RULES_RULEBOOK_URL_NAME}"),
            ),
        )
        for legacy_path, target_url in cases:
            response = self.client.get(legacy_path)
            self.assertEqual(response.status_code, 301)
            self.assertEqual(response["Location"], target_url)

    def test_pk_zero_matrix_redirects_to_overview(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        response = self.client.get("/plugins/netbox-nsm/rulebooks/0/matrix/")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response["Location"],
            reverse(f"plugins:netbox_nsm:{ALL_RULES_RULEBOOK_URL_NAME}"),
        )

    def test_pk_zero_overview_matches_normal_rulebook_url_pattern(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        overview_url = reverse(f"plugins:netbox_nsm:{ALL_RULES_RULEBOOK_URL_NAME}")
        normal_url = reverse("plugins:netbox_nsm:rulebook", args=[self.rb.pk])
        self.assertTrue(overview_url.endswith("/rulebooks/0/"))
        self.assertTrue(normal_url.endswith(f"/rulebooks/{self.rb.pk}/"))
        response = self.client.get(overview_url)
        self.assertEqual(response.status_code, 200)

    def test_virtual_all_rules_fields_sorted_by_sort_order(self):
        rb_late = Rulebook.objects.create(
            name="ZZZ Late Policy",
            rulebook_type=RulebookTypeChoices.SECURITY_RULES,
        )
        ensure_system_rulebook_fields(rb_late)
        RulebookField.objects.create(
            rulebook=rb_late,
            slug="early_custom",
            name="ffdsssfs",
            sort_order=1,
            field_kind=RulebookFieldKind.OBJECT,
            placement="fixed",
        )
        fields = load_virtual_all_rules_fields_for_detail()
        slugs = [field.slug for field in fields]
        self.assertEqual(slugs[0], VIRTUAL_ALL_RULES_FIELD_SLUG)
        self.assertIn("early_custom", slugs)
        self.assertLess(slugs.index("early_custom"), slugs.index("description"))
        self.assertLess(slugs.index("early_custom"), slugs.index("name"))

    def test_all_rules_overview_fields_show_rulebook_row(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        response = self.client.get(
            reverse(f"plugins:netbox_nsm:{ALL_RULES_RULEBOOK_URL_NAME}")
        )
        content = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("nsm-rb-fields-table", content)
        rulebook_pos = content.find("Rulebook")
        index_pos = content.find(">Index<")
        self.assertGreater(index_pos, 0)
        self.assertLess(rulebook_pos, index_pos)
