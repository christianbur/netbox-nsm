"""Tests for NetBox ObjectChange / changelog integration."""

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from ipam.models import Prefix
from rest_framework import status

from core.models import ObjectChange
from netbox_nsm.models import (
    Rule,
    Rulebook,
    RulebookField,
    RulebookFieldKind,
    RuleObjectItem,
)
from netbox_nsm.tests.custom import APITestCase, ModelViewTestCase


def _objectchange_count(model, pk):
    ct = ContentType.objects.get_for_model(model)
    return ObjectChange.objects.filter(
        changed_object_type=ct, changed_object_id=pk
    ).count()


def _test_prefix():
    prefix = Prefix.objects.first()
    if prefix is None:
        prefix = Prefix.objects.create(prefix="10.0.0.0/24", status="active")
    return prefix


class RuleAssignmentChangelogTest(ModelViewTestCase):
    """Rule assignment changes via policy grid API should appear on Rule changelog."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.rulebook = Rulebook.objects.create(
            name="changelog-rb", rulebook_type="security_rules"
        )
        cls.rule = Rule.objects.create(
            rulebook=cls.rulebook,
            name="changelog-rule",
            index=10,
        )
        cls.field = RulebookField.objects.create(
            rulebook=cls.rulebook,
            slug="source",
            name="Source",
            field_kind=RulebookFieldKind.OBJECT,
        )
        cls.prefix = _test_prefix()
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)

    def test_rules_grid_column_save_creates_rule_objectchange(self):
        self.add_permissions("netbox_nsm.change_rule", "netbox_nsm.view_rule")
        RuleObjectItem.objects.create(
            rule=self.rule,
            field=self.field,
            content_type=self.prefix_ct,
            object_id=self.prefix.pk,
            exclude=False,
        )
        column_key = f"source::ct_{self.prefix_ct.id}"
        before = _objectchange_count(Rule, self.rule.pk)

        self.client.force_login(self.user)
        url = reverse(
            "plugins:netbox_nsm:rule_field_selections_api",
            kwargs={"pk": self.rule.pk},
        )
        response = self.client.post(
            f"{url}?column={column_key}",
            data={"selections": []},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        self.assertGreater(_objectchange_count(Rule, self.rule.pk), before)
        latest = (
            ObjectChange.objects.filter(
                changed_object_type=ContentType.objects.get_for_model(Rule),
                changed_object_id=self.rule.pk,
            )
            .order_by("-time")
            .first()
        )
        self.assertIn("object_items", latest.postchange_data or {})


class RulebookFieldChangelogAPITest(APITestCase):
    """RulebookField API CRUD should create ObjectChange records."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.rulebook = Rulebook.objects.create(
            name="field-changelog-rb", rulebook_type="security_rules"
        )

    def test_rulebook_field_api_create_logs_change(self):
        self.add_permissions(
            "netbox_nsm.view_rulebookfield",
            "netbox_nsm.add_rulebookfield",
        )
        url = reverse("plugins-api:netbox_nsm-api:rulebookfield-list")
        item_ct = ContentType.objects.get_for_model(RulebookField)
        before = ObjectChange.objects.filter(changed_object_type=item_ct).count()

        response = self.client.post(
            url,
            {
                "rulebook": self.rulebook.pk,
                "slug": "dest",
                "name": "Destination",
                "sort_order": 100,
                "placement": "destination",
                "field_kind": "object",
            },
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        self.assertEqual(
            ObjectChange.objects.filter(changed_object_type=item_ct).count(),
            before + 1,
        )


class RuleObjectItemChangelogAPITest(APITestCase):
    """RuleObjectItem API writes should create ObjectChange records."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.rulebook = Rulebook.objects.create(
            name="item-changelog-rb", rulebook_type="security_rules"
        )
        cls.rule = Rule.objects.create(
            rulebook=cls.rulebook, name="item-rule", index=10
        )
        cls.field = RulebookField.objects.create(
            rulebook=cls.rulebook,
            slug="source",
            name="Source",
            field_kind=RulebookFieldKind.OBJECT,
        )
        cls.prefix = _test_prefix()
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)

    def test_rule_object_item_api_create_logs_change(self):
        self.add_permissions(
            "netbox_nsm.view_ruleobjectitem",
            "netbox_nsm.add_ruleobjectitem",
        )
        url = reverse("plugins-api:netbox_nsm-api:ruleobjectitem-list")
        item_ct = ContentType.objects.get_for_model(RuleObjectItem)
        before = ObjectChange.objects.filter(changed_object_type=item_ct).count()

        response = self.client.post(
            url,
            {
                "rule": self.rule.pk,
                "field": self.field.pk,
                "content_type": "ipam.prefix",
                "object_id": self.prefix.pk,
                "exclude": False,
            },
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        self.assertEqual(
            ObjectChange.objects.filter(changed_object_type=item_ct).count(),
            before + 1,
        )
