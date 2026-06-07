"""UI functional tests: rulebook, type config, rules, and panel object links."""

from unittest import mock

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from ipam.models import Prefix
from netbox.api.exceptions import SerializerNotFound
from utilities.api import get_serializer_for_model as _real_get_serializer_for_model

from netbox_nsm.models import (
    MatchingClassChoices,
    ObjectLink,
    Rule,
    Rulebook,
    TypeConfig,
)
from netbox_nsm.models.object_link import LinkPropagationChoices
from netbox_nsm.tests.form_helpers import rulebook_post_data
from netbox_nsm.tests.object_link_helpers import create_object_link_with_custom_object_b
from utilities.testing import TestCase
from utilities.testing.utils import post_data


def _get_serializer_raise_for_custom_objects(model, *args, **kwargs):
    if (
        getattr(model, "_meta", None)
        and model._meta.app_label == "netbox_custom_objects"
    ):
        raise SerializerNotFound(
            f"Could not determine serializer for {model._meta.label_lower}"
        )
    return _real_get_serializer_for_model(model, *args, **kwargs)


def _prefix(value):
    prefix = Prefix.objects.filter(prefix=value).first()
    if prefix is None:
        prefix = Prefix.objects.create(prefix=value, status="active")
    return prefix


class RulebookViewCrudTests(TestCase):
    """Create, edit, and delete rulebooks via the plugin UI."""

    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="ui-crud-rulebook",
            rulebook_type="security_rules",
        )

    def test_create_rulebook_via_ui(self):
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.add_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook_add")
        response = self.client.post(
            url,
            rulebook_post_data(
                name="ui-new-rulebook",
                matrix_tab_enabled="1",
                description="created in UI test",
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        created = Rulebook.objects.get(name="ui-new-rulebook")
        self.assertEqual(created.description, "created in UI test")

    def test_edit_rulebook_via_ui(self):
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.change_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook_edit", args=[self.rulebook.pk])
        response = self.client.post(
            url,
            rulebook_post_data(
                name="ui-crud-rulebook-renamed",
                description="updated",
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.rulebook.refresh_from_db()
        self.assertEqual(self.rulebook.name, "ui-crud-rulebook-renamed")
        self.assertEqual(self.rulebook.description, "updated")

    def test_edit_form_shows_hide_when_matrix_tab_disabled(self):
        self.rulebook.matrix_tab_enabled = False
        self.rulebook.save(update_fields=["matrix_tab_enabled"])
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.change_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook_edit", args=[self.rulebook.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertContains(
            response,
            '<option value="0"\n selected\n>Hide</option>',
        )

    def test_detail_shows_matrix_tab_hide(self):
        self.rulebook.matrix_tab_enabled = False
        self.rulebook.save(update_fields=["matrix_tab_enabled"])
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook", args=[self.rulebook.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertContains(response, "Matrix tab")
        self.assertContains(response, "Hide")

    def test_edit_rulebook_matrix_tab_hide_via_ui(self):
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.change_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook_edit", args=[self.rulebook.pk])
        response = self.client.post(
            url,
            rulebook_post_data(
                name=self.rulebook.name,
                matrix_tab_enabled="0",
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.rulebook.refresh_from_db()
        self.assertFalse(self.rulebook.matrix_tab_enabled)

    def test_delete_rulebook_via_ui(self):
        rb = Rulebook.objects.create(
            name="ui-del-rulebook",
            rulebook_type="security_rules",
        )
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.delete_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook_delete", args=[rb.pk])
        response = self.client.post(url, post_data({"confirm": True}))
        self.assertEqual(response.status_code, 302, response.content)
        self.assertFalse(Rulebook.objects.filter(pk=rb.pk).exists())

    def test_delete_rulebook_with_rules_is_blocked(self):
        rb = Rulebook.objects.create(
            name="ui-del-rulebook-blocked",
            rulebook_type="security_rules",
        )
        Rule.objects.create(rulebook=rb, name="blocking-rule", index=10)
        list_url = reverse("plugins:netbox_nsm:rulebook_list")
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.delete_rulebook")
        delete_url = (
            reverse("plugins:netbox_nsm:rulebook_delete", args=[rb.pk])
            + f"?return_url={list_url}"
        )
        response = self.client.get(delete_url, follow=True)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(Rulebook.objects.filter(pk=rb.pk).exists())
        content = response.content.decode()
        self.assertIn("cannot be deleted", content)
        self.assertIn("1 rule", content)

    def test_rulebook_detail_hides_delete_when_rules_present(self):
        rb = Rulebook.objects.create(
            name="ui-detail-del-blocked",
            rulebook_type="security_rules",
        )
        Rule.objects.create(rulebook=rb, name="keep-rulebook", index=10)
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.delete_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook", args=[rb.pk])
        content = self.client.get(url).content.decode()
        delete_url = reverse("plugins:netbox_nsm:rulebook_delete", args=[rb.pk])
        self.assertNotIn(delete_url, content)

    def test_rulebook_detail_shows_delete_when_empty(self):
        rb = Rulebook.objects.create(
            name="ui-detail-del-allowed",
            rulebook_type="security_rules",
        )
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.delete_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook", args=[rb.pk])
        content = self.client.get(url).content.decode()
        delete_url = reverse("plugins:netbox_nsm:rulebook_delete", args=[rb.pk])
        self.assertIn(delete_url, content)

    def test_rulebook_header_actions_only_on_primary_tab(self):
        rb = Rulebook.objects.create(
            name="ui-tab-actions",
            rulebook_type="security_rules",
        )
        Rule.objects.create(rulebook=rb, name="tab-action-rule", index=10)
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.view_rule",
            "netbox_nsm.change_rulebook",
            "netbox_nsm.delete_rulebook",
        )
        edit_url = reverse("plugins:netbox_nsm:rulebook_edit", args=[rb.pk])
        delete_url = reverse("plugins:netbox_nsm:rulebook_delete", args=[rb.pk])

        detail = self.client.get(
            reverse("plugins:netbox_nsm:rulebook", args=[rb.pk])
        ).content.decode()
        self.assertIn(edit_url, detail)
        self.assertNotIn(delete_url, detail)

        rules = self.client.get(
            reverse("plugins:netbox_nsm:rulebook_rules", args=[rb.pk])
        ).content.decode()
        self.assertNotIn(edit_url, rules)
        self.assertNotIn(delete_url, rules)

        matrix = self.client.get(
            reverse("plugins:netbox_nsm:rulebook_matrix", args=[rb.pk])
        ).content.decode()
        self.assertNotIn(edit_url, matrix)
        self.assertNotIn(delete_url, matrix)


class TypeConfigViewCrudTests(TestCase):
    """Create, edit, and delete TypeConfig entries via the plugin UI."""

    @classmethod
    def setUpTestData(cls):
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)
        cls.type_config = TypeConfig.objects.create(
            name="UI Test Zones",
            content_type=cls.prefix_ct,
            matching_class=MatchingClassChoices.OTHER,
            display_template="{name}",
            panel_slugs=["source"],
        )

    def test_list_hides_bulk_actions(self):
        self.add_permissions("netbox_nsm.view_typeconfig")
        response = self.client.get(reverse("plugins:netbox_nsm:typeconfig_list"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("UI Test Zones", content)
        self.assertNotIn('aria-label="Select all"', content)
        self.assertNotIn("Edit Selected", content)
        self.assertNotIn("Delete Selected", content)

    def test_create_typeconfig_via_ui(self):
        self.add_permissions("netbox_nsm.view_typeconfig", "netbox_nsm.add_typeconfig")
        ct = ContentType.objects.get(app_label="ipam", model="vlan")
        url = reverse("plugins:netbox_nsm:typeconfig_add")
        response = self.client.post(
            url,
            post_data(
                {
                    "name": "UI VLAN Type",
                    "content_type": ct,
                    "matching_class": MatchingClassChoices.ZONE,
                    "display_template": "{name}",
                    "panel_slugs": ["destination"],
                    "order_id": 50,
                }
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        created = TypeConfig.objects.get(name="UI VLAN Type")
        self.assertEqual(created.content_type_id, ct.pk)
        self.assertEqual(created.matching_class, MatchingClassChoices.ZONE)

    def test_edit_typeconfig_via_ui(self):
        self.add_permissions(
            "netbox_nsm.view_typeconfig", "netbox_nsm.change_typeconfig"
        )
        url = reverse("plugins:netbox_nsm:typeconfig_edit", args=[self.type_config.pk])
        response = self.client.post(
            url,
            post_data(
                {
                    "name": "UI Test Zones Renamed",
                    "matching_class": MatchingClassChoices.OTHER,
                    "display_template": "{name}",
                    "panel_slugs": ["source", "destination"],
                    "order_id": 20,
                }
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.type_config.refresh_from_db()
        self.assertEqual(self.type_config.name, "UI Test Zones Renamed")
        self.assertEqual(self.type_config.order_id, 20)

    def test_delete_typeconfig_via_ui(self):
        tc = TypeConfig.objects.create(
            name="UI Delete Me",
            content_type=ContentType.objects.get(app_label="ipam", model="vrf"),
            matching_class=MatchingClassChoices.INFO,
        )
        self.add_permissions(
            "netbox_nsm.view_typeconfig", "netbox_nsm.delete_typeconfig"
        )
        url = reverse("plugins:netbox_nsm:typeconfig_delete", args=[tc.pk])
        response = self.client.post(url, post_data({"confirm": True}))
        self.assertEqual(response.status_code, 302, response.content)
        self.assertFalse(TypeConfig.objects.filter(pk=tc.pk).exists())


class RuleViewCrudTests(TestCase):
    """Create, edit, and delete rules via the plugin UI."""

    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="ui-rule-crud-rb",
            rulebook_type="security_rules",
        )
        cls.rule = Rule.objects.create(
            rulebook=cls.rulebook,
            name="ui-crud-rule",
            index=10,
        )

    def test_create_rule_via_ui(self):
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.view_rule",
            "netbox_nsm.add_rule",
        )
        url = reverse("plugins:netbox_nsm:rule_add")
        response = self.client.post(
            url,
            post_data(
                {
                    "rulebook": self.rulebook,
                    "name": "ui-new-rule",
                    "index": 20,
                    "enabled": "1",
                    "description": "",
                    "comments": "",
                    "area_selections": "[]",
                    "virtual_group_config": "{}",
                }
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        created = Rule.objects.get(name="ui-new-rule", rulebook=self.rulebook)
        self.assertEqual(created.index, 20)
        self.assertTrue(created.enabled)

    def test_edit_rule_via_ui(self):
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.view_rule",
            "netbox_nsm.change_rule",
        )
        url = reverse("plugins:netbox_nsm:rule_edit", args=[self.rule.pk])
        response = self.client.post(
            url,
            post_data(
                {
                    "name": "ui-crud-rule-renamed",
                    "index": 15,
                    "enabled": "0",
                    "description": "edited",
                    "comments": "",
                    "area_selections": "[]",
                    "virtual_group_config": "{}",
                }
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.name, "ui-crud-rule-renamed")
        self.assertEqual(self.rule.index, 15)
        self.assertFalse(self.rule.enabled)
        self.assertEqual(self.rule.description, "edited")

    def test_delete_rule_via_ui(self):
        rule = Rule.objects.create(
            rulebook=self.rulebook,
            name="ui-del-rule",
            index=99,
        )
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.view_rule",
            "netbox_nsm.delete_rule",
        )
        url = reverse("plugins:netbox_nsm:rule_delete", args=[rule.pk])
        response = self.client.post(url, post_data({"confirm": True}))
        self.assertEqual(response.status_code, 302, response.content)
        self.assertFalse(Rule.objects.filter(pk=rule.pk).exists())
        self.assertEqual(
            response.url,
            reverse("plugins:netbox_nsm:rulebook_rules", args=[self.rulebook.pk]),
        )

    def test_bulk_delete_rules_confirmation_page(self):
        rule_a = Rule.objects.create(
            rulebook=self.rulebook,
            name="ui-bulk-del-a",
            index=40,
        )
        rule_b = Rule.objects.create(
            rulebook=self.rulebook,
            name="ui-bulk-del-b",
            index=50,
        )
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.view_rule",
            "netbox_nsm.delete_rule",
        )
        url = reverse("plugins:netbox_nsm:rule_bulk_delete")
        return_url = reverse(
            "plugins:netbox_nsm:rulebook_rules", args=[self.rulebook.pk]
        )
        response = self.client.post(
            url,
            post_data(
                {
                    "pk": [rule_a.pk, rule_b.pk],
                    "return_url": return_url,
                }
            ),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(
            Rule.objects.filter(pk__in=[rule_a.pk, rule_b.pk]).count(),
            2,
        )


class ObjectLinkPanelViewTests(TestCase):
    """Assign, edit, and delete Security Panel object links via UI routes."""

    @classmethod
    def setUpTestData(cls):
        cls.prefix_a = _prefix("10.50.0.0/24")
        cls.prefix_b = _prefix("10.50.1.0/24")
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)
        cls.type_config = TypeConfig.objects.create(
            name="Panel Prefix Zones",
            content_type=cls.prefix_ct,
            matching_class=MatchingClassChoices.ZONE,
            display_template="{prefix}",
            panel_slugs=["source"],
        )
        cls.return_url = reverse("ipam:prefix", args=[cls.prefix_a.pk])

    def test_assign_object_link_via_panel(self):
        url = reverse("plugins:netbox_nsm:object_link_assign")
        response = self.client.post(
            url,
            {
                "object_a_type_id": self.prefix_ct.pk,
                "object_a_id": self.prefix_a.pk,
                "object_b_type": self.prefix_ct.pk,
                "object_b_id": self.prefix_b.pk,
                "propagation": LinkPropagationChoices.DIRECT,
                "comment": "panel assign test",
                "return_url": self.return_url,
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        link = ObjectLink.objects.get(
            object_a_type=self.prefix_ct,
            object_a_id=self.prefix_a.pk,
            object_b_type=self.prefix_ct,
            object_b_id=self.prefix_b.pk,
        )
        self.assertEqual(link.comment, "panel assign test")

    def test_edit_object_link_via_panel(self):
        link = ObjectLink.objects.create(
            object_a_type=self.prefix_ct,
            object_a_id=self.prefix_a.pk,
            object_b_type=self.prefix_ct,
            object_b_id=self.prefix_b.pk,
            comment="before",
            propagation=LinkPropagationChoices.DIRECT,
        )
        url = reverse("plugins:netbox_nsm:object_link_edit", args=[link.pk])
        response = self.client.post(
            url,
            {
                "comment": "after edit",
                "propagation": LinkPropagationChoices.INHERIT_IPAM,
                "return_url": self.return_url,
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        link.refresh_from_db()
        self.assertEqual(link.comment, "after edit")
        self.assertEqual(link.propagation, LinkPropagationChoices.INHERIT_IPAM)

    def test_delete_object_link_via_panel(self):
        link = ObjectLink.objects.create(
            object_a_type=self.prefix_ct,
            object_a_id=self.prefix_a.pk,
            object_b_type=self.prefix_ct,
            object_b_id=self.prefix_b.pk,
            comment="delete me",
        )
        url = reverse("plugins:netbox_nsm:object_link_delete", args=[link.pk])
        response = self.client.post(
            url,
            {
                "confirm": True,
                "return_url": self.return_url,
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.assertFalse(ObjectLink.objects.filter(pk=link.pk).exists())

    @mock.patch(
        "netbox_nsm.api.serializers_.object_link.get_serializer_for_model",
        side_effect=_get_serializer_raise_for_custom_objects,
    )
    def test_delete_object_link_custom_object_b_via_panel(self, _mock_get_serializer):
        link, _custom_instance = create_object_link_with_custom_object_b(self.prefix_a)
        url = reverse("plugins:netbox_nsm:object_link_delete", args=[link.pk])
        response = self.client.post(
            url,
            {
                "confirm": True,
                "return_url": self.return_url,
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.assertFalse(ObjectLink.objects.filter(pk=link.pk).exists())
