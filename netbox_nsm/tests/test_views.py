"""UI functional tests: rulebook, type config, rules, and panel object links."""

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from ipam.models import Prefix

from netbox_nsm.models import (
    MatchingClassChoices,
    ObjectLink,
    Rule,
    Rulebook,
    TypeConfig,
)
from netbox_nsm.models.object_link import LinkPropagationChoices
from utilities.testing import TestCase
from utilities.testing.utils import post_data


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
            post_data(
                {
                    "name": "ui-new-rulebook",
                    "rulebook_type": "security_rules",
                    "description": "created in UI test",
                    "comments": "",
                }
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
            post_data(
                {
                    "name": "ui-crud-rulebook-renamed",
                    "rulebook_type": "security_rules",
                    "description": "updated",
                    "comments": "",
                }
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.rulebook.refresh_from_db()
        self.assertEqual(self.rulebook.name, "ui-crud-rulebook-renamed")
        self.assertEqual(self.rulebook.description, "updated")

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
