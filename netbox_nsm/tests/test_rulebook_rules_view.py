"""Rules tab — HTML rules table."""

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from urllib.parse import quote

from netbox_nsm.models import (
    Rule,
    Rulebook,
    RulebookField,
    RulebookFieldKind,
    RulebookFieldType,
    TypeConfig,
)
from netbox_nsm.rulebook_rules_tab import RULES_HTML_ROW_LIMIT
from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields
from utilities.testing import TestCase


class RulebookRulesViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="Rules Tab Test",
            rulebook_type="security_rules",
        )
        ensure_system_rulebook_fields(cls.rulebook)
        cls.type_config, _ = TypeConfig.objects.get_or_create(
            content_type=ContentType.objects.order_by("pk").first(),
            defaults={"name": "Rules View Type"},
        )
        cls.object_field = RulebookField.objects.create(
            rulebook=cls.rulebook,
            slug="destination",
            name="Destination",
            placement="destination",
            field_kind=RulebookFieldKind.OBJECT,
            visible=True,
            sort_order=60,
        )
        RulebookFieldType.objects.create(
            field=cls.object_field,
            type_config=cls.type_config,
            visible=True,
        )
        Rule.objects.create(
            rulebook=cls.rulebook,
            name="rules-demo",
            index=10,
            enabled=True,
            description="Alpha → Beta",
        )

    def test_rules_tab_label_on_rulebook_page(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook", args=[self.rulebook.pk])
        content = self.client.get(url).content.decode()
        rules_url = reverse("plugins:netbox_nsm:rulebook_rules", args=[self.rulebook.pk])
        self.assertIn(rules_url, content)

        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook_rules", args=[self.rulebook.pk])
        content = self.client.get(url).content.decode()
        self.assertIn('class="w-1"', content)
        self.assertIn('name="pk"', content)
        self.assertIn('value="{}"'.format(self.rulebook.rules.first().pk), content)

    def test_filter_q_is_applied_to_rules_rows(self):
        Rule.objects.create(
            rulebook=self.rulebook,
            name="alpha-match",
            index=1,
            enabled=True,
        )
        Rule.objects.create(
            rulebook=self.rulebook,
            name="beta-other",
            index=2,
            enabled=True,
        )
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook_rules", args=[self.rulebook.pk])
        content = self.client.get(f"{url}?filter_q=Name(alpha)").content.decode()
        self.assertIn("alpha-match", content)
        self.assertNotIn("beta-other", content)

    def test_rules_tab_renders_ag_grid_aligned_table(self):
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.change_rule",
            "netbox_nsm.delete_rule",
        )
        url = reverse("plugins:netbox_nsm:rulebook_rules", args=[self.rulebook.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('id="rules"', content)
        self.assertIn("nsm-rules-table", content)
        self.assertIn("object-list", content)
        self.assertIn("htmx-container table-responsive", content)
        self.assertIn("rulebook_rules.css", content)
        self.assertIn("nsm-rules-head-row--filter", content)
        self.assertNotIn("nsm-rules-head-row--sub", content)
        self.assertNotIn("nsm-rules-th--group-label", content)
        self.assertIn("(Destination)", content)
        self.assertIn("nsm-rules-filter-input", content)
        self.assertIn("nsm-rules-col-resize-handle", content)
        self.assertIn('data-col-id="status"', content)
        self.assertIn("nsm-rules-filter-apply", content)
        self.assertIn("rulebook_rules_columns.js", content)
        self.assertNotIn("nsm-rules-bullet", content)
        self.assertIn("table-hover", content)
        self.assertNotIn("table-bordered", content)
        self.assertNotIn("nsm-rules-th--group text-uppercase", content)
        self.assertNotIn("text-decoration-none text-uppercase small", content)
        self.assertIn('class="badge text-bg-blue"', content)
        self.assertIn("nsm-ag-chrome-bar", content)
        self.assertNotIn("nsm-ag-filter-query", content)
        self.assertIn("Export CSV", content)
        self.assertNotIn("badge rounded-pill text-bg-primary", content)
        self.assertIn("Add Rule", content)
        self.assertNotIn("Open AG Grid", content)
        self.assertIn("Per Page", content)
        self.assertIn("sticky-actions", content)
        self.assertIn("Edit Selected", content)
        self.assertIn("Delete Selected", content)
        self.assertIn('class="w-1"', content)
        self.assertIn('name="pk"', content)
        self.assertIn("Destination", content)
        self.assertIn("data-col-id=", content)

    def test_delete_action_includes_return_url_to_rules_tab(self):
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.change_rule",
            "netbox_nsm.delete_rule",
        )
        url = reverse("plugins:netbox_nsm:rulebook_rules", args=[self.rulebook.pk])
        content = self.client.get(url).content.decode()
        rule = self.rulebook.rules.first()
        delete_path = reverse("plugins:netbox_nsm:rule_delete", args=[rule.pk])
        self.assertIn(
            f'{delete_path}?return_url={quote(url, safe="")}',
            content,
        )
        self.assertIn("data-nsm-filter-value=", content)
        self.assertIn("filterColumnMap", content)
        self.assertIn("nsm-ag-description-lines", content)
        self.assertNotIn("nsm-viz-table", content)

    def test_rules_page_does_not_mount_ag_grid(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook_rules", args=[self.rulebook.pk])
        response = self.client.get(url)
        content = response.content.decode()
        self.assertNotIn("nsm-rules-ag-grid", content)
        self.assertNotIn("nsm-rulebook-rules-grid-data", content)
        self.assertNotIn("rulebook_rules_grid.js", content)
        self.assertNotIn("nsm-viz-table", content)
        self.assertNotIn("matrix_ag_grid.js", content)

    def test_rules_columns_change_when_field_layout_changes(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook_rules", args=[self.rulebook.pk])

        with_field = self.client.get(url).content.decode()
        self.assertIn("(Destination)", with_field)
        self.assertIn('data-col-id="destination::', with_field)

        self.object_field.visible = False
        self.object_field.save(update_fields=["visible"])

        without_field = self.client.get(url).content.decode()
        self.assertNotIn("(Destination)", without_field)
        self.assertNotIn('data-col-id="destination::', without_field)

    def test_rules_pagination_shows_second_page(self):
        Rule.objects.bulk_create(
            [
                Rule(
                    rulebook=self.rulebook,
                    name=f"view-page-rule-{idx}",
                    index=idx,
                    enabled=True,
                )
                for idx in range(RULES_HTML_ROW_LIMIT + 12)
            ]
        )
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook_rules", args=[self.rulebook.pk])
        page_url = f"{url}?per_page=25"

        page1 = self.client.get(page_url).content.decode()
        self.assertIn("Per Page", page1)
        self.assertIn("Showing 1-", page1)
        self.assertIn("view-page-rule-0", page1)
        self.assertNotIn("view-page-rule-36", page1)

        page2 = self.client.get(f"{page_url}&page=2").content.decode()
        self.assertIn("Showing ", page2)
        self.assertIn("view-page-rule-36", page2)
        self.assertNotIn("view-page-rule-0", page2)
        self.assertIn('rel="prev"', page2)

        page1_nav = self.client.get(page_url).content.decode()
        self.assertIn('rel="next"', page1_nav)
