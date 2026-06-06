"""UI CRUD tests for security object groups."""

from django.urls import reverse

from netbox_nsm.models import ObjectGroup
from utilities.testing import TestCase
from utilities.testing.utils import post_data


class ObjectGroupViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.group = ObjectGroup.objects.create(
            name="ui-group-crud",
            field_slugs=["source"],
            description="initial",
        )

    def test_create_object_group_via_ui(self):
        self.add_permissions(
            "netbox_nsm.view_objectgroup",
            "netbox_nsm.add_objectgroup",
        )
        url = reverse("plugins:netbox_nsm:objectgroup_add")
        response = self.client.post(
            url,
            post_data(
                {
                    "name": "ui-new-group",
                    "field_slugs": ["destination"],
                    "color": "#aabbcc",
                    "description": "created in UI",
                }
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        created = ObjectGroup.objects.get(name="ui-new-group")
        self.assertEqual(created.field_slugs, ["destination"])
        self.assertEqual(created.color, "#aabbcc")

    def test_edit_object_group_via_ui(self):
        self.add_permissions(
            "netbox_nsm.view_objectgroup",
            "netbox_nsm.change_objectgroup",
        )
        url = reverse("plugins:netbox_nsm:objectgroup_edit", args=[self.group.pk])
        response = self.client.post(
            url,
            post_data(
                {
                    "name": "ui-group-crud-renamed",
                    "field_slugs": ["source", "destination"],
                    "color": "",
                    "description": "updated",
                }
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.group.refresh_from_db()
        self.assertEqual(self.group.name, "ui-group-crud-renamed")
        self.assertEqual(self.group.description, "updated")

    def test_delete_object_group_via_ui(self):
        group = ObjectGroup.objects.create(name="ui-del-group")
        self.add_permissions(
            "netbox_nsm.view_objectgroup",
            "netbox_nsm.delete_objectgroup",
        )
        url = reverse("plugins:netbox_nsm:objectgroup_delete", args=[group.pk])
        response = self.client.post(url, post_data({"confirm": True}))
        self.assertEqual(response.status_code, 302, response.content)
        self.assertFalse(ObjectGroup.objects.filter(pk=group.pk).exists())

    def test_object_group_list_renders(self):
        self.add_permissions("netbox_nsm.view_objectgroup")
        url = reverse("plugins:netbox_nsm:objectgroup_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertContains(response, "ui-group-crud")
