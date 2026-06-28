"""Rulebook list: COT-backed virtual rows."""

from django.urls import reverse

from netbox_nsm.rulebooks.object_actions import AddCotRulebook
from netbox_nsm.rulebooks.permissions import RulebookListProxy
from netbox_nsm.tests.rulebook_permission_helpers import (
    grant_rulebook_cot_perms,
    grant_rulebook_list_access,
)
from utilities.testing import TestCase


class RulebookListViewTests(TestCase):
    def test_list_renders_without_native_rulebooks(self):
        grant_rulebook_list_access(self)
        response = self.client.get(reverse("plugins:netbox_nsm:rulebook_list"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context)

    def test_list_hides_add_without_permission(self):
        grant_rulebook_list_access(self)
        response = self.client.get(reverse("plugins:netbox_nsm:rulebook_list"))
        self.assertEqual(response.context["actions"], [])

    def test_list_shows_add_with_permission(self):
        grant_rulebook_list_access(self)
        self.add_permissions("netbox_custom_objects.add_customobjecttype")
        response = self.client.get(reverse("plugins:netbox_nsm:rulebook_list"))
        self.assertEqual(response.context["actions"], [AddCotRulebook])
        self.assertEqual(
            AddCotRulebook.get_url(RulebookListProxy),
            reverse("plugins:netbox_nsm:cot_rulebook_add"),
        )

    def test_list_access_with_create_permission_and_no_rulebooks(self):
        self.add_permissions("netbox_custom_objects.add_customobjecttype")
        response = self.client.get(reverse("plugins:netbox_nsm:rulebook_list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["table"].data), [])

    def test_list_access_with_per_cot_view_permission(self):
        from netbox_custom_objects.models import CustomObjectType

        from netbox_nsm.rulebooks.templates import RULEBOOK_GROUP

        cot = CustomObjectType.objects.create(
            name="nsm_rb_list_perm_test",
            slug="nsm_rb_list_perm_test",
            verbose_name="List Perm Test",
            group_name=RULEBOOK_GROUP,
        )
        grant_rulebook_cot_perms(self, cot, view=True)
        response = self.client.get(reverse("plugins:netbox_nsm:rulebook_list"))
        self.assertEqual(response.status_code, 200)

    def test_list_row_shows_edit_delete_actions(self):
        from netbox_custom_objects.models import CustomObjectType

        from netbox_nsm.rulebooks.templates import RULEBOOK_GROUP

        cot = CustomObjectType.objects.create(
            name="nsm_rb_list_actions_test",
            slug="nsm_rb_list_actions_test",
            verbose_name="List Actions Test",
            group_name=RULEBOOK_GROUP,
        )
        grant_rulebook_cot_perms(self, cot, view=True, change=True)
        self.add_permissions("netbox_custom_objects.delete_customobjecttype")
        response = self.client.get(reverse("plugins:netbox_nsm:rulebook_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "btn-warning")
        self.assertContains(
            response,
            reverse(
                "plugins:netbox_nsm:cot_rulebook_delete",
                kwargs={"slug": cot.slug},
            ),
        )
        self.assertContains(response, f"/plugins/netbox-nsm/rulebooks/cot/{cot.slug}/?edit=1")
