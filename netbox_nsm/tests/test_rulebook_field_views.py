"""UI CRUD tests for rulebook fields and field types."""

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from netbox_nsm.models import Rulebook, RulebookField, RulebookFieldType, TypeConfig
from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields
from utilities.testing import TestCase
from utilities.testing.utils import post_data


class RulebookFieldViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="ui-field-rb",
            rulebook_type="security_rules",
        )
        ensure_system_rulebook_fields(cls.rulebook)
        cls.field = RulebookField.objects.create(
            rulebook=cls.rulebook,
            slug="custom_field",
            name="Custom Field",
            placement="fixed",
        )
        cls.type_config, _ = TypeConfig.objects.get_or_create(
            content_type=ContentType.objects.order_by("pk").first(),
            defaults={"name": "Field View Type"},
        )

    def test_add_rulebook_field_via_ui(self):
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.change_rulebook",
        )
        url = (
            reverse("plugins:netbox_nsm:rulebookfield_add")
            + f"?rulebook={self.rulebook.pk}"
        )
        response = self.client.post(
            url,
            post_data(
                {
                    "rulebook": self.rulebook.pk,
                    "name": "UI Added Field",
                    "placement": "source",
                    "visible": True,
                    "sort_order": 100,
                }
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        created = RulebookField.objects.get(
            rulebook=self.rulebook,
            name="UI Added Field",
        )
        self.assertEqual(created.placement, "source")

    def test_edit_rulebook_field_via_ui(self):
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.change_rulebook",
        )
        url = reverse(
            "plugins:netbox_nsm:rulebookfield_edit",
            args=[self.field.pk],
        )
        response = self.client.post(
            url,
            post_data(
                {
                    "rulebook": self.rulebook.pk,
                    "name": "Custom Field Renamed",
                    "placement": "destination",
                    "visible": True,
                    "sort_order": 50,
                }
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.field.refresh_from_db()
        self.assertEqual(self.field.name, "Custom Field Renamed")
        self.assertEqual(self.field.placement, "destination")

    def test_delete_rulebook_field_via_ui(self):
        field = RulebookField.objects.create(
            rulebook=self.rulebook,
            slug="delete_me",
            name="Delete Me",
            placement="fixed",
        )
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.change_rulebook",
        )
        url = reverse(
            "plugins:netbox_nsm:rulebookfield_delete",
            args=[field.pk],
        )
        response = self.client.post(url, post_data({"confirm": True}))
        self.assertEqual(response.status_code, 302, response.content)
        self.assertFalse(RulebookField.objects.filter(pk=field.pk).exists())


class RulebookFieldTypeViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="ui-ft-rb",
            rulebook_type="security_rules",
        )
        cls.field = RulebookField.objects.create(
            rulebook=cls.rulebook,
            slug="services",
            name="Services",
            placement="fixed",
        )
        cls.type_config, _ = TypeConfig.objects.get_or_create(
            content_type=ContentType.objects.order_by("pk").first(),
            defaults={"name": "Field Type View TC"},
        )
        cls.field_type = RulebookFieldType.objects.create(
            field=cls.field,
            type_config=cls.type_config,
            sort_order=10,
        )

    def test_add_field_type_via_ui(self):
        tc = TypeConfig.objects.create(
            name="Extra Field Type TC",
            content_type=ContentType.objects.get(app_label="ipam", model="vrf"),
        )
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.change_rulebook",
        )
        url = (
            reverse("plugins:netbox_nsm:rulebookfieldtype_add")
            + f"?field={self.field.pk}"
        )
        response = self.client.post(
            url,
            post_data(
                {
                    "field": self.field.pk,
                    "type_config": tc.pk,
                    "sort_order": 20,
                    "visible": True,
                }
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.assertTrue(
            RulebookFieldType.objects.filter(field=self.field, type_config=tc).exists()
        )

    def test_delete_field_type_via_ui(self):
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.change_rulebook",
        )
        url = reverse(
            "plugins:netbox_nsm:rulebookfieldtype_delete",
            args=[self.field_type.pk],
        )
        response = self.client.post(url, post_data({"confirm": True}))
        self.assertEqual(response.status_code, 302, response.content)
        self.assertFalse(
            RulebookFieldType.objects.filter(pk=self.field_type.pk).exists()
        )
