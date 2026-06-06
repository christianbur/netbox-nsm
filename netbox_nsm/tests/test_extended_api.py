"""REST API tests for models beyond core rulebook/rule/link CRUD."""

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from ipam.models import Prefix
from rest_framework import status

from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Site

from netbox_nsm.models import (
    ObjectGroup,
    Rule,
    Rulebook,
    RulebookAssignment,
    RulebookField,
    RulebookFieldKind,
    RuleGroupItem,
    RuleObjectItem,
)
from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields
from netbox_nsm.tests.custom import APITestCase
from netbox_nsm.tests.test_api_integration import (
    _API_CRUD_PERMS,
    _RulebookPluginAPITestMixin,
)


def _api(name, **kwargs):
    return reverse(f"plugins-api:netbox_nsm-api:{name}", kwargs=kwargs)


def _prefix(value):
    prefix = Prefix.objects.filter(prefix=value).first()
    if prefix is None:
        prefix = Prefix.objects.create(prefix=value, status="active")
    return prefix


def _device(name="nsm-api-test-device"):
    site, _ = Site.objects.get_or_create(
        name="NSM API Test Site",
        defaults={"slug": "nsm-api-test-site"},
    )
    manufacturer, _ = Manufacturer.objects.get_or_create(
        name="NSM API Test Mfr",
        defaults={"slug": "nsm-api-test-mfr"},
    )
    device_type, _ = DeviceType.objects.get_or_create(
        manufacturer=manufacturer,
        model="NSM API Test Model",
        defaults={"slug": "nsm-api-test-model"},
    )
    role, _ = DeviceRole.objects.get_or_create(
        name="NSM API Test Role",
        defaults={"slug": "nsm-api-test-role"},
    )
    device, _ = Device.objects.get_or_create(
        name=name,
        defaults={
            "device_type": device_type,
            "role": role,
            "site": site,
            "status": "active",
        },
    )
    return device


class ObjectGroupAPITest(_RulebookPluginAPITestMixin, APITestCase):
    """CRUD for security object groups."""

    def test_object_group_crud(self):
        self._grant(
            *_API_CRUD_PERMS,
            "netbox_nsm.add_objectgroup",
            "netbox_nsm.change_objectgroup",
            "netbox_nsm.delete_objectgroup",
        )
        list_url = _api("objectgroup-list")

        response = self._post_json(
            list_url,
            {
                "name": "api-object-group",
                "field_slugs": ["source", "destination"],
                "description": "via api",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        group_id = response.data["id"]

        detail_url = _api("objectgroup-detail", pk=group_id)
        response = self._patch_json(
            detail_url,
            {"name": "api-object-group-upd", "field_slugs": ["source"]},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["name"], "api-object-group-upd")

        response = self._delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ObjectGroup.objects.filter(pk=group_id).exists())


class RulebookAssignmentAPITest(_RulebookPluginAPITestMixin, APITestCase):
    """CRUD for rulebook assignments on devices."""

    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="api-assignment-rb",
            rulebook_type="security_rules",
        )
        cls.device = _device()
        cls.device_ct = ContentType.objects.get_for_model(Device)

    def test_rulebook_assignment_crud(self):
        self._grant(
            *_API_CRUD_PERMS,
            "netbox_nsm.add_rulebookassignment",
            "netbox_nsm.change_rulebookassignment",
            "netbox_nsm.delete_rulebookassignment",
        )
        list_url = _api("rulebookassignment-list")

        response = self._post_json(
            list_url,
            {
                "rulebook": {"id": self.rulebook.pk},
                "assigned_object_type": "dcim.device",
                "assigned_object_id": self.device.pk,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        assignment_id = response.data["id"]

        detail_url = _api("rulebookassignment-detail", pk=assignment_id)
        response = self.client.get(detail_url, **self.header)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["assigned_object_id"], self.device.pk)

        response = self._delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(RulebookAssignment.objects.filter(pk=assignment_id).exists())


class RuleObjectItemsAPITest(_RulebookPluginAPITestMixin, APITestCase):
    """CRUD for rule object items and group items."""

    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="api-roi-rb",
            rulebook_type="security_rules",
        )
        ensure_system_rulebook_fields(cls.rulebook)
        cls.rule = Rule.objects.create(
            rulebook=cls.rulebook,
            name="api-roi-rule",
            index=10,
        )
        cls.field = RulebookField.objects.create(
            rulebook=cls.rulebook,
            slug="source",
            name="Source",
            placement="source",
            field_kind=RulebookFieldKind.OBJECT,
            visible=True,
        )
        cls.prefix = _prefix("10.70.0.0/24")
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)
        cls.group = ObjectGroup.objects.create(
            name="api-roi-group",
            field_slugs=["source"],
        )

    def test_rule_object_item_crud(self):
        self._grant(
            *_API_CRUD_PERMS,
            "netbox_nsm.add_ruleobjectitem",
            "netbox_nsm.change_ruleobjectitem",
            "netbox_nsm.delete_ruleobjectitem",
        )
        list_url = _api("ruleobjectitem-list")

        response = self._post_json(
            list_url,
            {
                "rule": self.rule.pk,
                "field": self.field.pk,
                "content_type": "ipam.prefix",
                "object_id": self.prefix.pk,
                "exclude": False,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        item_id = response.data["id"]

        detail_url = _api("ruleobjectitem-detail", pk=item_id)
        response = self._patch_json(detail_url, {"exclude": True})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data["exclude"])

        response = self._delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(RuleObjectItem.objects.filter(pk=item_id).exists())

    def test_rule_group_item_crud(self):
        self._grant(
            *_API_CRUD_PERMS,
            "netbox_nsm.add_rulegroupitem",
            "netbox_nsm.change_rulegroupitem",
            "netbox_nsm.delete_rulegroupitem",
        )
        list_url = _api("rulegroupitem-list")

        response = self._post_json(
            list_url,
            {
                "rule": self.rule.pk,
                "field": self.field.pk,
                "security_group": self.group.pk,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        item_id = response.data["id"]

        detail_url = _api("rulegroupitem-detail", pk=item_id)
        response = self.client.get(detail_url, **self.header)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["security_group"], self.group.pk)

        response = self._delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(RuleGroupItem.objects.filter(pk=item_id).exists())
