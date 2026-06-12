"""Tests for NSM-scoped Custom Object URLs."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.urls import reverse

from netbox_nsm.objects.cot_routes import (
    NSM_OBJECTS_GROUP_NAME,
    apply_nsm_object_url_patches,
    cot_belongs_to_nsm_objects_menu,
    is_nsm_object_menu_slug,
    nsm_object_reverse,
)


class CotRoutesTests(SimpleTestCase):
    @patch("netbox_nsm.objects.cot_routes._custom_object_type_model")
    def test_nsm_zone_is_menu_slug_when_in_group(self, model_accessor):
        model_accessor.return_value.objects.filter.return_value.exists.return_value = True
        self.assertTrue(is_nsm_object_menu_slug("nsm_zone"))

    @patch("netbox_nsm.objects.cot_routes._custom_object_type_model")
    def test_other_group_slug_is_not_menu_slug(self, model_accessor):
        model_accessor.return_value.objects.filter.return_value.exists.return_value = False
        self.assertFalse(is_nsm_object_menu_slug("nsm_object_link"))

    def test_cot_belongs_to_nsm_objects_menu(self):
        self.assertTrue(
            cot_belongs_to_nsm_objects_menu(
                SimpleNamespace(group_name=NSM_OBJECTS_GROUP_NAME)
            )
        )
        self.assertFalse(
            cot_belongs_to_nsm_objects_menu(SimpleNamespace(group_name="NSM Panel"))
        )

    def test_nsm_object_reverse_list(self):
        url = nsm_object_reverse("list", "nsm_zone")
        self.assertIn("/plugins/netbox-nsm/objects/nsm_zone/", url)

    @patch("netbox_custom_objects.models.CustomObjectType")
    @patch("netbox_custom_objects.models.CustomObject")
    def test_patched_get_absolute_url_uses_nsm_route(self, custom_object, cot_type):
        apply_nsm_object_url_patches()

        instance = SimpleNamespace(
            pk=42,
            custom_object_type=SimpleNamespace(
                slug="nsm_zone",
                group_name=NSM_OBJECTS_GROUP_NAME,
            ),
        )
        url = custom_object.get_absolute_url(instance)
        self.assertEqual(
            url,
            reverse(
                "plugins:netbox_nsm:nsm_object",
                kwargs={"custom_object_type": "nsm_zone", "pk": 42},
            ),
        )

    @patch("netbox_custom_objects.models.CustomObjectType")
    @patch("netbox_custom_objects.models.CustomObject")
    def test_patched_get_viewname_uses_nsm_route(self, custom_object, cot_type):
        apply_nsm_object_url_patches()
        from netbox_custom_objects.utilities import get_viewname

        model = MagicMock()
        model.custom_object_type = SimpleNamespace(
            slug="nsm_zone",
            group_name=NSM_OBJECTS_GROUP_NAME,
        )
        self.assertEqual(
            get_viewname(model, action="add"),
            "plugins:netbox_nsm:nsm_object_add",
        )

    @patch("netbox_custom_objects.models.CustomObjectType")
    @patch("netbox_custom_objects.models.CustomObject")
    def test_patched_get_absolute_url_skips_other_groups(self, custom_object, cot_type):
        original_url = "/plugins/custom-objects/nsm_object_link/7/"
        original_get_absolute_url = MagicMock(return_value=original_url)
        custom_object.get_absolute_url = original_get_absolute_url
        apply_nsm_object_url_patches()

        instance = SimpleNamespace(
            pk=7,
            custom_object_type=SimpleNamespace(
                slug="nsm_object_link",
                group_name="NSM Panel",
            ),
        )
        url = custom_object.get_absolute_url(instance)
        self.assertEqual(url, original_url)
        original_get_absolute_url.assert_called_once_with(instance)
