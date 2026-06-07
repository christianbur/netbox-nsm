"""Rulebook schema copy (list action → add form + field layout)."""

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils.html import escape
from ipam.models import Prefix

from netbox_nsm.models import (
    MatchingClassChoices,
    Rulebook,
    RulebookField,
    RulebookFieldKind,
    RulebookFieldType,
    RulebookTypeChoices,
    TypeConfig,
)
from netbox_nsm.rulebook_copy import COPY_SCHEMA_PARAM, rulebook_schema_copy_add_url
from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields, load_rulebook_fields_for_detail
from netbox_nsm.tests.form_helpers import rulebook_post_data
from utilities.testing import TestCase


class RulebookSchemaCopyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.source = Rulebook.objects.create(
            name="schema-source",
            rulebook_type=RulebookTypeChoices.SECURITY_RULES,
            status="active",
            description="source description",
            mgmt_url="https://fw.example.test/",
            rule_comment_template="Rule {rule_name}",
        )
        ensure_system_rulebook_fields(cls.source)
        cls.zone_field = RulebookField.objects.create(
            rulebook=cls.source,
            slug="zones",
            name="Zones",
            sort_order=10,
            placement="source",
            field_kind=RulebookFieldKind.OBJECT,
            visible=True,
            facet_mode="value",
        )
        cls.type_config = TypeConfig.objects.create(
            name="Copy Test Zones",
            content_type=ContentType.objects.get_for_model(Prefix),
            matching_class=MatchingClassChoices.ZONE,
            display_template="{name}",
            panel_slugs=["source"],
        )
        RulebookFieldType.objects.create(
            field=cls.zone_field,
            type_config=cls.type_config,
            sort_order=10,
            visible=True,
        )

    def test_list_shows_copy_schema_action(self):
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.add_rulebook")
        response = self.client.get(reverse("plugins:netbox_nsm:rulebook_list"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Copy schema", content)
        copy_url = rulebook_schema_copy_add_url(
            self.source,
            return_url=reverse("plugins:netbox_nsm:rulebook_list"),
        )
        self.assertIn(escape(copy_url), content)

    def test_add_form_prefills_metadata_but_not_name(self):
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.add_rulebook")
        url = rulebook_schema_copy_add_url(self.source)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('name="description"', content)
        self.assertIn("source description", content)
        self.assertIn("https://fw.example.test/", content)
        self.assertIn(COPY_SCHEMA_PARAM, content)
        self.assertNotIn('value="schema-source"', content)

    def test_add_form_includes_hidden_copy_schema_field(self):
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.add_rulebook")
        url = rulebook_schema_copy_add_url(self.source)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(f'name="{COPY_SCHEMA_PARAM}"', content)
        self.assertIn(f'value="{self.source.pk}"', content)

    def test_create_rulebook_copies_field_layout(self):
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.add_rulebook",
        )
        url = reverse("plugins:netbox_nsm:rulebook_add")
        response = self.client.post(
            url,
            rulebook_post_data(
                name="schema-copy-target",
                description="source description",
                mgmt_url="https://fw.example.test/",
                **{COPY_SCHEMA_PARAM: self.source.pk},
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        target = Rulebook.objects.get(name="schema-copy-target")
        source_fields = {
            field.slug: field for field in load_rulebook_fields_for_detail(self.source)
        }
        target_fields = {
            field.slug: field for field in load_rulebook_fields_for_detail(target)
        }
        self.assertIn("zones", target_fields)
        self.assertEqual(
            target_fields["zones"].name,
            source_fields["zones"].name,
        )
        copied_types = list(target_fields["zones"].type_configs.all())
        self.assertEqual(len(copied_types), 1)
        self.assertEqual(copied_types[0].type_config_id, self.type_config.pk)
