"""Zone Matrix tab — classic HTML heatmap."""

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from ipam.models import Prefix

from netbox_nsm.models import (
    Rule,
    Rulebook,
    RulebookField,
    RulebookFieldKind,
    RulebookFieldType,
    RuleObjectItem,
    TypeConfig,
)
from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields
from utilities.testing import TestCase


class RulebookMatrixViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="Matrix Tab Test",
            rulebook_type="security_rules",
        )
        ensure_system_rulebook_fields(cls.rulebook)
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)
        cls.type_config, _ = TypeConfig.objects.update_or_create(
            content_type=cls.prefix_ct,
            defaults={"name": "Zones", "display_template": "{description}"},
        )
        for slug, placement in (("source", "source"), ("destination", "destination")):
            field = RulebookField.objects.create(
                rulebook=cls.rulebook,
                slug=slug,
                name=slug.capitalize(),
                placement=placement,
                field_kind=RulebookFieldKind.OBJECT,
                visible=True,
                sort_order=50 if slug == "source" else 60,
            )
            RulebookFieldType.objects.create(
                field=field,
                type_config=cls.type_config,
                visible=True,
            )
        Rule.objects.create(
            rulebook=cls.rulebook,
            name="matrix-demo",
            index=1,
            enabled=True,
        )
        cls.zone_a = Prefix.objects.create(prefix="10.0.1.0/24", status="active", description="demo-0001")
        cls.zone_b = Prefix.objects.create(prefix="10.0.3.0/24", status="active", description="demo-0003")
        cls.source_field = RulebookField.objects.get(rulebook=cls.rulebook, slug="source")
        cls.destination_field = RulebookField.objects.get(rulebook=cls.rulebook, slug="destination")
        cls.rule_ab = Rule.objects.create(
            rulebook=cls.rulebook,
            name="ab-1",
            index=2,
            enabled=True,
        )
        cls.rule_ab2 = Rule.objects.create(
            rulebook=cls.rulebook,
            name="ab-2",
            index=3,
            enabled=True,
        )
        cls.rule_ba = Rule.objects.create(
            rulebook=cls.rulebook,
            name="ba-1",
            index=4,
            enabled=True,
        )
        for rule, src, dst in (
            (cls.rule_ab, cls.zone_a, cls.zone_b),
            (cls.rule_ab2, cls.zone_a, cls.zone_b),
            (cls.rule_ba, cls.zone_b, cls.zone_a),
        ):
            RuleObjectItem.objects.create(
                rule=rule,
                field=cls.source_field,
                content_type=cls.prefix_ct,
                object_id=src.pk,
            )
            RuleObjectItem.objects.create(
                rule=rule,
                field=cls.destination_field,
                content_type=cls.prefix_ct,
                object_id=dst.pk,
            )

    def test_matrix_tab_renders_classic_html_matrix(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook_matrix", args=[self.rulebook.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("nsm-viz-table", content)
        self.assertIn("rulebook_matrix.js", content)
        self.assertIn("nsm-matrix-filter-form", content)
        self.assertNotIn('id="matrix-obj-type"', content)
        self.assertIn(f'name="obj_type" value="{self.prefix_ct.pk}"', content)
        self.assertNotIn('id="matrix-mode"', content)
        self.assertNotIn('name="mode"', content)
        self.assertIn("nsm-viz-filter-field", content)
        self.assertIn("nsm-matrix-axis-select", content)
        self.assertIn("Apply filters", content)

    def test_matrix_has_no_ag_grid_fallback(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook_matrix", args=[self.rulebook.pk])
        content = self.client.get(url).content.decode()
        self.assertNotIn("nsm-matrix-ag-grid", content)
        self.assertNotIn("matrix_ag_grid.js", content)

    def test_matrix_tab_appears_in_rulebook_nav(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook", args=[self.rulebook.pk])
        content = self.client.get(url).content.decode()
        matrix_url = reverse("plugins:netbox_nsm:rulebook_matrix", args=[self.rulebook.pk])
        self.assertIn(matrix_url, content)
        self.assertIn("Matrix", content)

    def test_matrix_url_no_longer_redirects_to_rules(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook_matrix", args=[self.rulebook.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("nsm-viz-table", response.content.decode())

    def test_matrix_cell_links_use_column_filters_not_filter_q(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook_matrix", args=[self.rulebook.pk])
        url = f"{url}?obj_type={self.prefix_ct.pk}"
        content = self.client.get(url).content.decode()
        ct_token = f"ct_{self.prefix_ct.pk}"
        self.assertIn(f"f_source__{ct_token}=demo-0001", content)
        self.assertIn(f"f_destination__{ct_token}=demo-0003", content)
        self.assertIn(f"f_source__{ct_token}=demo-0003", content)
        self.assertIn(f"f_destination__{ct_token}=demo-0001", content)
        self.assertNotIn("filter_q=", content)
        self.assertIn("data-rules-href=", content)

    def test_matrix_cell_count_is_row_to_column_only(self):
        """Each matrix cell badge counts row→column rules only."""
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook_matrix", args=[self.rulebook.pk])
        url = f"{url}?obj_type={self.prefix_ct.pk}"
        content = self.client.get(url).content.decode()
        ct_token = f"ct_{self.prefix_ct.pk}"
        fwd_pair = (
            f"f_source__{ct_token}=demo-0001&amp;f_destination__{ct_token}=demo-0003"
        )
        idx = content.find(fwd_pair)
        self.assertGreater(idx, -1, msg="Expected demo-0001→demo-0003 filter link")
        snippet = content[idx : idx + 400]
        self.assertIn('title="2 Rules">2</a>', snippet)
        self.assertNotIn('title="3 Rules">3</a>', snippet)
