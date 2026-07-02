"""Tests for COT rulebook rules JSON export (bundle ``objects`` records)."""

import json
import uuid

from django.test import RequestFactory
from django.urls import reverse

from extras.choices import CustomFieldTypeChoices
from utilities.testing import TestCase

from netbox_nsm.bundles.bundle_extensions import format_portable_ref
from netbox_nsm.rulebooks.rules_export import (
    build_cot_rulebook_rules_export_bundle,
    collect_cot_rulebook_export_instances,
    cot_instance_to_bundle_record,
)
from netbox_nsm.rulebooks.rules_layout import _PREFETCHED_M2M_ATTR
from netbox_nsm.rulebooks.templates import RULEBOOK_GROUP
from netbox_nsm.rulebooks.virtual_cot import VirtualCotRulebook
from netbox_nsm.tests.rulebook_permission_helpers import grant_rulebook_cot_perms


class FormatPortableRefTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField

        zone_slug = f"nsm_zone_export_{uuid.uuid4().hex[:8]}"
        cls.zone_cot = CustomObjectType.objects.create(
            name=zone_slug,
            slug=zone_slug,
            verbose_name="Export Zone",
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.zone_cot,
            name="name",
            label="Name",
            type=CustomFieldTypeChoices.TYPE_TEXT,
            primary=True,
            required=True,
        )
        cls.zone = cls.zone_cot.get_model().objects.create(name="trust")

    def test_formats_cot_slug_and_object_name(self):
        self.assertEqual(
            format_portable_ref(self.zone),
            f"{self.zone_cot.slug}/trust",
        )

    def test_rejects_non_custom_object_instance(self):
        from dcim.models import Site

        with self.assertRaises(ValueError):
            format_portable_ref(Site.objects.create(name="site-a", slug="site-a"))


class CotInstanceToBundleRecordTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from core.models import ObjectType
        from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField

        zone_slug = f"nsm_zone_rb_export_{uuid.uuid4().hex[:8]}"
        cls.zone_cot = CustomObjectType.objects.create(
            name=zone_slug,
            slug=zone_slug,
            verbose_name="Export Zone",
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.zone_cot,
            name="name",
            label="Name",
            type=CustomFieldTypeChoices.TYPE_TEXT,
            primary=True,
            required=True,
        )
        cls.zone = cls.zone_cot.get_model().objects.create(name="dmz")
        zone_object_type = ObjectType.objects.get(
            app_label="netbox_custom_objects",
            model=cls.zone._meta.model_name,
        )

        rb_slug = f"nsm_rb_export_{uuid.uuid4().hex[:8]}"
        cls.rulebook = CustomObjectType.objects.create(
            name=rb_slug,
            slug=rb_slug,
            verbose_name="Export Test Rulebook",
            group_name=RULEBOOK_GROUP,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.rulebook,
            name="index",
            label="Index",
            type=CustomFieldTypeChoices.TYPE_INTEGER,
            primary=True,
            required=True,
            weight=1,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.rulebook,
            name="status",
            label="Status",
            type=CustomFieldTypeChoices.TYPE_BOOLEAN,
            required=False,
            weight=2,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.rulebook,
            name="name",
            label="Name",
            type=CustomFieldTypeChoices.TYPE_TEXT,
            required=True,
            weight=3,
        )
        src_field = CustomObjectTypeField.objects.create(
            custom_object_type=cls.rulebook,
            name="source_zones",
            label="Zones",
            type=CustomFieldTypeChoices.TYPE_MULTIOBJECT,
            is_polymorphic=True,
            weight=11,
        )
        src_field.related_object_types.set([zone_object_type])
        cls.rule_model = cls.rulebook.get_model()
        cls.rule = cls.rule_model.objects.create(
            index=7,
            status=False,
            name="export-rule",
        )

    def test_includes_index_status_and_portable_refs(self):
        setattr(
            self.rule,
            _PREFETCHED_M2M_ATTR,
            {"source_zones": [self.zone]},
        )
        record = cot_instance_to_bundle_record(self.rule, self.rulebook)
        self.assertEqual(record["index"], 7)
        self.assertFalse(record["status"])
        self.assertEqual(record["name"], "export-rule")
        self.assertEqual(
            record["source_zones"],
            [f"{self.zone_cot.slug}/dmz"],
        )


class CotRulebookRulesExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField

        rb_slug = f"nsm_rb_export_view_{uuid.uuid4().hex[:8]}"
        cls.rulebook = CustomObjectType.objects.create(
            name=rb_slug,
            slug=rb_slug,
            verbose_name="Export View Rulebook",
            group_name=RULEBOOK_GROUP,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.rulebook,
            name="index",
            label="Index",
            type=CustomFieldTypeChoices.TYPE_INTEGER,
            primary=True,
            required=True,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.rulebook,
            name="status",
            label="Status",
            type=CustomFieldTypeChoices.TYPE_BOOLEAN,
            required=False,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.rulebook,
            name="name",
            label="Name",
            type=CustomFieldTypeChoices.TYPE_TEXT,
            required=True,
        )
        cls.rule_model = cls.rulebook.get_model()
        cls.rule_model.objects.create(index=2, status=True, name="rule-b")
        cls.rule_model.objects.create(index=1, status=True, name="rule-a")
        cls.virtual_rb = VirtualCotRulebook(cls.rulebook, rule_count=2)

    def _request(self, **params):
        path = reverse(
            "plugins:netbox_nsm:cot_rulebook_rules_export",
            kwargs={"slug": self.rulebook.slug},
        )
        request = RequestFactory().get(path, params)
        request.user = self.user
        return request

    def test_collect_respects_name_filter(self):
        request = self._request(**{"f_name": "rule-a"})
        instances = collect_cot_rulebook_export_instances(request, self.virtual_rb)
        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0].name, "rule-a")

    def test_build_bundle_shape_and_sort(self):
        bundle = build_cot_rulebook_rules_export_bundle(
            self._request(),
            self.virtual_rb,
        )
        self.assertEqual(bundle["schema_type"], "nsm")
        self.assertEqual(bundle["schema_version"], "1")
        self.assertEqual(bundle["bundle_kind"], "schema")
        self.assertEqual(bundle["rulebook_slug"], self.rulebook.slug)
        self.assertEqual(len(bundle["objects"]), 1)
        entry = bundle["objects"][0]
        self.assertEqual(entry["type"], self.rulebook.slug)
        records = entry["records"]
        self.assertEqual(len(records), 2)
        self.assertEqual([row["index"] for row in records], [1, 2])
        self.assertEqual(records[0]["name"], "rule-a")

    def test_export_view_downloads_json_attachment(self):
        grant_rulebook_cot_perms(self, self.rulebook, view=True)
        url = reverse(
            "plugins:netbox_nsm:cot_rulebook_rules_export",
            kwargs={"slug": self.rulebook.slug},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json; charset=utf-8")
        self.assertIn("attachment", response["Content-Disposition"])
        data = json.loads(response.content)
        self.assertEqual(data["objects"][0]["type"], self.rulebook.slug)
        self.assertEqual(len(data["objects"][0]["records"]), 2)
