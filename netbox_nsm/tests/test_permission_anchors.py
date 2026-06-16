"""Permission-anchor models must not require physical database tables."""

from django.db import connection
from django.urls import reverse

from core.models import ObjectType
from netbox.models.features import model_is_public
from netbox_nsm.rulebooks.permissions import RulebookListProxy
from utilities.testing import TestCase


class PermissionAnchorTests(TestCase):
    def setUp(self):
        super().setUp()
        self.user.is_superuser = True
        self.user.save()

    def test_rulebook_list_proxy_is_netbox_private(self):
        self.assertTrue(getattr(RulebookListProxy, "_netbox_private"))
        self.assertFalse(model_is_public(RulebookListProxy))

    def test_rulebook_list_proxy_object_type_is_not_public(self):
        ot = ObjectType.objects.get(app_label="netbox_nsm", model="rulebooklistproxy")
        self.assertFalse(ot.public)
        self.assertNotIn(
            ot,
            ObjectType.objects.public().filter(app_label="netbox_nsm"),
        )

    def test_no_physical_tables_required(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN (
                    'netbox_nsm_typeconfig',
                    'netbox_nsm_rulebooklistproxy'
                  )
                """
            )
            self.assertEqual(cursor.fetchall(), [])

    def test_system_view_without_anchor_tables(self):
        response = self.client.get(reverse("core:system"))
        self.assertEqual(response.status_code, 200)
