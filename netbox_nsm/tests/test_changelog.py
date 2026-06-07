"""Tests for NetBox ObjectChange / changelog integration."""

import json

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from ipam.models import Prefix
from rest_framework import status

from core.choices import ObjectChangeActionChoices
from core.models import ObjectChange
from netbox_nsm.changelog_utils import (
    _infer_rules_layout_changelog_action,
    _rules_layout_changelog_slice,
    describe_rule_assignment_changes,
    describe_rulebook_fields_layout_changes,
    describe_rulebook_rules_changes,
    describe_type_config_changes,
)
from netbox_nsm.models import (
    Rule,
    Rulebook,
    RulebookField,
    RulebookFieldKind,
    RuleObjectItem,
    TypeConfig,
)
from netbox_nsm.tests.custom import APITestCase, ModelViewTestCase
from netbox_nsm.tests.form_helpers import rulebook_post_data
from utilities.testing.utils import post_data


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
    """Rule assignment changes via rules grid API should appear on Rule changelog."""

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
        self.assertIsInstance(latest.postchange_data.get("object_items"), dict)
        self.assertTrue(latest.message)

        rb_latest = (
            ObjectChange.objects.filter(
                changed_object_type=ContentType.objects.get_for_model(Rulebook),
                changed_object_id=self.rulebook.pk,
            )
            .order_by("-time")
            .first()
        )
        self.assertIn("rules_layout", rb_latest.postchange_data or {})
        self.assertIsInstance(rb_latest.postchange_data.get("rules_layout"), dict)
        self.assertTrue(rb_latest.message)


class RulebookRulesLayoutChangelogTest(ModelViewTestCase):
    """Rule CRUD and assignments should appear on the parent Rulebook changelog."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.rulebook = Rulebook.objects.create(
            name="rules-layout-changelog-rb",
            rulebook_type="security_rules",
        )
        cls.field = RulebookField.objects.create(
            rulebook=cls.rulebook,
            slug="source",
            name="Source",
            field_kind=RulebookFieldKind.OBJECT,
            placement="source",
        )
        cls.rule = Rule.objects.create(
            rulebook=cls.rulebook,
            name="rules-layout-rule",
            index=10,
        )
        cls.prefix = _test_prefix()
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)

    def test_rule_edit_form_records_rules_layout_on_rulebook(self):
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.view_rule",
            "netbox_nsm.change_rule",
        )
        rb_ct = ContentType.objects.get_for_model(Rulebook)
        before = ObjectChange.objects.filter(
            changed_object_type=rb_ct,
            changed_object_id=self.rulebook.pk,
        ).count()
        selections = [
            {
                "area": "source",
                "placement": "source",
                "kind": "object",
                "id": f"{self.prefix_ct.id}.{self.prefix.pk}",
                "name": str(self.prefix),
            }
        ]
        url = reverse("plugins:netbox_nsm:rule_edit", args=[self.rule.pk])
        response = self.client.post(
            url,
            post_data(
                {
                    "name": "rules-layout-rule-renamed",
                    "index": 20,
                    "enabled": "1",
                    "description": "",
                    "comments": "",
                    "area_selections": json.dumps(selections),
                    "virtual_group_config": "{}",
                }
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.assertGreater(
            ObjectChange.objects.filter(
                changed_object_type=rb_ct,
                changed_object_id=self.rulebook.pk,
            ).count(),
            before,
        )
        latest = (
            ObjectChange.objects.filter(
                changed_object_type=rb_ct,
                changed_object_id=self.rulebook.pk,
            )
            .order_by("-time")
            .first()
        )
        rules_layout = latest.postchange_data.get("rules_layout") or {}
        self.assertIsInstance(rules_layout, dict)
        self.assertIn(str(self.rule.pk), rules_layout)
        self.assertTrue(latest.message)
        self.assertIn("rules-layout-rule-renamed", latest.message.lower())

    def test_rule_delete_records_delta_on_rulebook(self):
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.view_rule",
            "netbox_nsm.delete_rule",
        )
        rb_ct = ContentType.objects.get_for_model(Rulebook)
        before = ObjectChange.objects.filter(
            changed_object_type=rb_ct,
            changed_object_id=self.rulebook.pk,
        ).count()
        url = reverse("plugins:netbox_nsm:rule_delete", args=[self.rule.pk])
        response = self.client.post(url, post_data({"confirm": True}))
        self.assertEqual(response.status_code, 302, response.content)
        self.assertGreater(
            ObjectChange.objects.filter(
                changed_object_type=rb_ct,
                changed_object_id=self.rulebook.pk,
            ).count(),
            before,
        )
        latest = (
            ObjectChange.objects.filter(
                changed_object_type=rb_ct,
                changed_object_id=self.rulebook.pk,
            )
            .order_by("-time")
            .first()
        )
        self.assertIn("Removed rule", latest.message)
        self.assertEqual(latest.action, ObjectChangeActionChoices.ACTION_DELETE)
        pre_rules = latest.prechange_data.get("rules_layout") or {}
        post_rules = latest.postchange_data.get("rules_layout") or {}
        self.assertIn(str(self.rule.pk), pre_rules)
        self.assertNotIn(str(self.rule.pk), post_rules)
        self.assertEqual(len(pre_rules), 1)

    def test_rules_layout_changelog_slice_keeps_only_changed_rules(self):
        pre = {
            "rules_layout": {
                "1": {"name": "a", "index": 1, "enabled": True},
                "2": {"name": "b", "index": 2, "enabled": True},
            }
        }
        post = {
            "rules_layout": {
                "1": {"name": "a", "index": 1, "enabled": True},
                "2": {"name": "b-renamed", "index": 2, "enabled": True},
            }
        }
        pre_slice, post_slice = _rules_layout_changelog_slice(pre, post)
        self.assertEqual(set(pre_slice), {"2"})
        self.assertEqual(set(post_slice), {"2"})
        self.assertEqual(pre_slice["2"]["name"], "b")
        self.assertEqual(post_slice["2"]["name"], "b-renamed")

    def test_infer_rules_layout_changelog_action(self):
        delete_pre = {"1": {"name": "removed"}}
        delete_post = {}
        self.assertEqual(
            _infer_rules_layout_changelog_action(delete_pre, delete_post),
            ObjectChangeActionChoices.ACTION_DELETE,
        )

        create_pre = {}
        create_post = {"2": {"name": "added"}}
        self.assertEqual(
            _infer_rules_layout_changelog_action(create_pre, create_post),
            ObjectChangeActionChoices.ACTION_CREATE,
        )

        update_pre = {"3": {"name": "old"}}
        update_post = {"3": {"name": "new"}}
        self.assertEqual(
            _infer_rules_layout_changelog_action(update_pre, update_post),
            ObjectChangeActionChoices.ACTION_UPDATE,
        )

        mixed_pre = {"1": {"name": "removed"}, "2": {"name": "old"}}
        mixed_post = {"2": {"name": "new"}}
        self.assertEqual(
            _infer_rules_layout_changelog_action(mixed_pre, mixed_post),
            ObjectChangeActionChoices.ACTION_UPDATE,
        )


class TypeConfigChangelogTest(ModelViewTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)
        cls.type_config = TypeConfig.objects.create(
            name="changelog-type",
            content_type=cls.prefix_ct,
            panel_slugs=["source"],
        )

    def test_typeconfig_edit_serializes_panel_slugs_as_dict(self):
        self.add_permissions(
            "netbox_nsm.view_typeconfig",
            "netbox_nsm.change_typeconfig",
        )
        tc_ct = ContentType.objects.get_for_model(TypeConfig)
        url = reverse(
            "plugins:netbox_nsm:typeconfig_edit",
            args=[self.type_config.pk],
        )
        response = self.client.post(
            url,
            post_data(
                {
                    "name": self.type_config.name,
                    "matching_class": "",
                    "display_template": "{name}",
                    "panel_slugs": ["source", "destination"],
                    "order_id": 100,
                }
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        latest = (
            ObjectChange.objects.filter(
                changed_object_type=tc_ct,
                changed_object_id=self.type_config.pk,
            )
            .order_by("-time")
            .first()
        )
        self.assertIsInstance(latest.postchange_data.get("panel_slugs"), dict)
        self.assertIn("destination", latest.postchange_data["panel_slugs"])
        self.assertTrue(latest.message)
        self.assertIn("destination", latest.message.lower())


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

        field_id = response.data["id"]
        self.assertEqual(
            ObjectChange.objects.filter(
                changed_object_type=item_ct,
                changed_object_id=field_id,
            ).count(),
            1,
        )
        rb_ct = ContentType.objects.get_for_model(Rulebook)
        latest_rb = (
            ObjectChange.objects.filter(
                changed_object_type=rb_ct,
                changed_object_id=self.rulebook.pk,
            )
            .order_by("-time")
            .first()
        )
        self.assertIsInstance(latest_rb.postchange_data.get("fields_layout"), dict)
        self.assertTrue(latest_rb.message)


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


class RulebookFieldsLayoutChangelogTest(ModelViewTestCase):
    """Rulebook field UI edits should appear on the parent Rulebook changelog."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.rulebook = Rulebook.objects.create(
            name="layout-changelog-rb",
            rulebook_type="security_rules",
        )
        cls.field = RulebookField.objects.create(
            rulebook=cls.rulebook,
            slug="source",
            name="Source",
            placement="source",
            sort_order=10,
        )

    def test_field_edit_records_rulebook_objectchange(self):
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.change_rulebook",
        )
        rb_ct = ContentType.objects.get_for_model(Rulebook)
        before = ObjectChange.objects.filter(
            changed_object_type=rb_ct,
            changed_object_id=self.rulebook.pk,
        ).count()
        url = reverse(
            "plugins:netbox_nsm:rulebookfield_edit",
            args=[self.field.pk],
        )
        response = self.client.post(
            url,
            post_data(
                {
                    "rulebook": self.rulebook.pk,
                    "name": "Source Renamed",
                    "placement": "source",
                    "visible": True,
                    "sort_order": 15,
                }
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.assertGreater(
            ObjectChange.objects.filter(
                changed_object_type=rb_ct,
                changed_object_id=self.rulebook.pk,
            ).count(),
            before,
        )
        latest = (
            ObjectChange.objects.filter(
                changed_object_type=rb_ct,
                changed_object_id=self.rulebook.pk,
            )
            .order_by("-time")
            .first()
        )
        self.assertIn("fields_layout", latest.postchange_data or {})
        self.assertIsInstance(latest.postchange_data.get("fields_layout"), dict)
        self.assertIn("source", latest.postchange_data["fields_layout"])
        self.assertNotIn("rules_layout", latest.prechange_data or {})
        self.assertNotIn("rules_layout", latest.postchange_data or {})
        self.assertTrue(latest.message)


class RulebookMetadataChangelogTest(ModelViewTestCase):
    """Metadata edits via the rulebook form must not snapshot all rules."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.rulebook = Rulebook.objects.create(
            name="metadata-changelog-rb",
            rulebook_type="security_rules",
        )
        Rule.objects.create(
            rulebook=cls.rulebook, name="metadata-changelog-rule", index=10
        )

    def test_rulebook_edit_omits_layout_snapshots_from_changelog(self):
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.change_rulebook")
        rb_ct = ContentType.objects.get_for_model(Rulebook)
        url = reverse("plugins:netbox_nsm:rulebook_edit", args=[self.rulebook.pk])
        response = self.client.post(
            url,
            rulebook_post_data(
                name="metadata-changelog-rb",
                matrix_tab_enabled="0",
                description="updated metadata",
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        latest = (
            ObjectChange.objects.filter(
                changed_object_type=rb_ct,
                changed_object_id=self.rulebook.pk,
            )
            .order_by("-time")
            .first()
        )
        post = latest.postchange_data or {}
        self.assertNotIn("rules_layout", post)
        self.assertNotIn("fields_layout", post)
        self.assertFalse(post.get("matrix_tab_enabled"))
        pre = latest.prechange_data or {}
        self.assertNotIn("rules_layout", pre)
        self.assertNotIn("fields_layout", pre)


class RuleEditorAssignmentChangelogTest(ModelViewTestCase):
    """Rule editor form saves should log object assignments on the Rule."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.rulebook = Rulebook.objects.create(
            name="editor-changelog-rb",
            rulebook_type="security_rules",
        )
        cls.field = RulebookField.objects.create(
            rulebook=cls.rulebook,
            slug="source",
            name="Source",
            field_kind=RulebookFieldKind.OBJECT,
            placement="source",
        )
        cls.rule = Rule.objects.create(
            rulebook=cls.rulebook,
            name="editor-changelog-rule",
            index=10,
        )
        cls.prefix = _test_prefix()
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)

    def test_rule_edit_form_records_object_items_on_changelog(self):
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.view_rule",
            "netbox_nsm.change_rule",
        )
        selections = [
            {
                "area": "source",
                "placement": "source",
                "kind": "object",
                "id": f"{self.prefix_ct.id}.{self.prefix.pk}",
                "name": str(self.prefix),
            }
        ]
        before = _objectchange_count(Rule, self.rule.pk)
        url = reverse("plugins:netbox_nsm:rule_edit", args=[self.rule.pk])
        response = self.client.post(
            url,
            post_data(
                {
                    "name": self.rule.name,
                    "index": self.rule.index,
                    "enabled": "1",
                    "description": "",
                    "comments": "",
                    "area_selections": json.dumps(selections),
                    "virtual_group_config": "{}",
                }
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
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
        self.assertIsInstance(latest.postchange_data.get("object_items"), dict)
        self.assertTrue(latest.message)
        self.assertTrue(
            RuleObjectItem.objects.filter(
                rule=self.rule,
                field=self.field,
                content_type=self.prefix_ct,
                object_id=self.prefix.pk,
            ).exists()
        )


class RulebookFieldsLayoutDiffTest(ModelViewTestCase):
    def test_describe_layout_changes_is_human_readable(self):
        pre = {
            "fields_layout": {
                "source": {
                    "name": "Source",
                    "sort_order": 10,
                    "types": {},
                }
            }
        }
        post = {
            "fields_layout": {
                "source": {
                    "name": "Source",
                    "sort_order": 15,
                    "types": {},
                }
            }
        }
        msg = describe_rulebook_fields_layout_changes(pre, post)
        self.assertIn("Source", msg)
        self.assertIn("sort_order", msg)
        self.assertIn("10", msg)
        self.assertIn("15", msg)


class RulebookRulesLayoutDiffTest(ModelViewTestCase):
    def test_describe_rules_layout_changes_is_human_readable(self):
        pre = {
            "rules_layout": {
                "1": {
                    "name": "Allow HTTP",
                    "index": 10,
                    "enabled": True,
                    "object_items": {},
                    "group_items": {},
                }
            }
        }
        post = {
            "rules_layout": {
                "1": {
                    "name": "Allow HTTPS",
                    "index": 10,
                    "enabled": True,
                    "object_items": {},
                    "group_items": {},
                }
            }
        }
        msg = describe_rulebook_rules_changes(pre, post)
        self.assertIn("Allow HTTP", msg)
        self.assertIn("Allow HTTPS", msg)


class RuleAssignmentDiffTest(ModelViewTestCase):
    def test_describe_assignment_changes_is_human_readable(self):
        prefix_ct = ContentType.objects.get_for_model(Prefix)
        key = f"source:ct_{prefix_ct.id}:5"
        pre = {"object_items": {}, "group_items": {}}
        post = {
            "object_items": {
                key: {
                    "field": "source",
                    "content_type": prefix_ct.id,
                    "object_id": 5,
                    "exclude": False,
                }
            },
            "group_items": {},
        }
        msg = describe_rule_assignment_changes(pre, post)
        self.assertIn("Added object", msg)
        self.assertIn(key, msg)


class TypeConfigDiffTest(ModelViewTestCase):
    def test_describe_type_config_changes_is_human_readable(self):
        pre = {"panel_slugs": {"source": True}, "panel_linkable_types": {}}
        post = {
            "panel_slugs": {"source": True, "destination": True},
            "panel_linkable_types": {},
        }
        msg = describe_type_config_changes(pre, post)
        self.assertIn('Added panel slug "destination"', msg)


class RuleObjectItemApiChangelogTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.rulebook = Rulebook.objects.create(
            name="api-changelog-rb",
            rulebook_type="security_rules",
        )
        cls.field = RulebookField.objects.create(
            rulebook=cls.rulebook,
            slug="source",
            name="Source",
            field_kind=RulebookFieldKind.OBJECT,
            placement="source",
        )
        cls.rule = Rule.objects.create(
            rulebook=cls.rulebook,
            name="api-changelog-rule",
            index=10,
        )
        cls.prefix = _test_prefix()
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)

    def test_rule_object_item_api_create_logs_parent_rule(self):
        self.add_permissions(
            "netbox_nsm.view_ruleobjectitem",
            "netbox_nsm.add_ruleobjectitem",
            "netbox_nsm.view_rule",
        )
        rule_ct = ContentType.objects.get_for_model(Rule)
        before = ObjectChange.objects.filter(
            changed_object_type=rule_ct,
            changed_object_id=self.rule.pk,
        ).count()
        url = reverse("plugins-api:netbox_nsm-api:ruleobjectitem-list")
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
        self.assertGreater(
            ObjectChange.objects.filter(
                changed_object_type=rule_ct,
                changed_object_id=self.rule.pk,
            ).count(),
            before,
        )
        latest = (
            ObjectChange.objects.filter(
                changed_object_type=rule_ct,
                changed_object_id=self.rule.pk,
            )
            .order_by("-time")
            .first()
        )
        self.assertIsInstance(latest.postchange_data.get("object_items"), dict)
        self.assertTrue(latest.message)
        self.assertIn("Added object", latest.message)


class TypeConfigApiChangelogTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)
        cls.type_config = TypeConfig.objects.create(
            name="api-changelog-type",
            content_type=cls.prefix_ct,
            panel_slugs=["source"],
        )

    def test_typeconfig_api_patch_sets_readable_message(self):
        self.add_permissions(
            "netbox_nsm.view_typeconfig",
            "netbox_nsm.change_typeconfig",
        )
        tc_ct = ContentType.objects.get_for_model(TypeConfig)
        url = reverse(
            "plugins-api:netbox_nsm-api:typeconfig-detail",
            kwargs={"pk": self.type_config.pk},
        )
        response = self.client.patch(
            url,
            {"panel_slugs": ["source", "destination"]},
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        latest = (
            ObjectChange.objects.filter(
                changed_object_type=tc_ct,
                changed_object_id=self.type_config.pk,
            )
            .order_by("-time")
            .first()
        )
        self.assertIsInstance(latest.postchange_data.get("panel_slugs"), dict)
        self.assertTrue(latest.message)
        self.assertIn("destination", latest.message.lower())


class ChangelogContentTypeLabelTest(ModelViewTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)
        cls.type_config = TypeConfig.objects.create(
            name="Addresses",
            content_type=cls.prefix_ct,
            panel_slugs=["source"],
        )
        cls.rulebook = Rulebook.objects.create(
            name="changelog-label-rb",
            rulebook_type="security_rules",
        )
        cls.field = RulebookField.objects.create(
            rulebook=cls.rulebook,
            slug="destination",
            name="Destination",
            field_kind=RulebookFieldKind.OBJECT,
            placement="destination",
        )
        cls.rule = Rule.objects.create(
            rulebook=cls.rulebook,
            name="changelog-label-rule",
            index=10,
        )
        cls.prefix = _test_prefix()
        RuleObjectItem.objects.create(
            rule=cls.rule,
            field=cls.field,
            content_type=cls.prefix_ct,
            object_id=cls.prefix.pk,
        )

    def test_rules_layout_uses_friendly_content_type_label(self):
        from netbox_nsm.display_utils import changelog_content_type_label
        from netbox_nsm.models.rulebook import _serialize_rule_object_items

        label = changelog_content_type_label(self.prefix_ct.id)
        self.assertIn("Addresses", label)
        self.assertNotIn("ipam.prefix", label)
        self.assertIn("›", label)

        items = _serialize_rule_object_items(self.rule)
        key = f"destination:ct_{self.prefix_ct.id}:{self.prefix.pk}"
        row = items[key]
        self.assertEqual(row["content_type_label"], label)
        self.assertEqual(row["object"], str(self.prefix))
