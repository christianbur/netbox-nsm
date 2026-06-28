"""Tests for NSM Custom Object URL helpers."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from netbox_nsm.objects.cot_routes import (
    NSM_OBJECTS_GROUP_NAME,
    cot_belongs_to_nsm_objects_menu,
    is_nsm_object_menu_slug,
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
