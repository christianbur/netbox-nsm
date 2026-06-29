"""Tests for NSM Custom Object URL helpers."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from netbox_nsm.objects.cot_routes import (
    apply_nsm_object_url_patches,
    cot_belongs_to_nsm_objects_menu,
    is_nsm_object_menu_slug,
)
from netbox_nsm.objects.nsm_config import merge_nsm_config_document_into_comments


class CotRoutesTests(SimpleTestCase):
    def test_nsm_zone_is_menu_slug_when_metadata_menu_is_objects(self):
        cot = SimpleNamespace(
            slug="nsm_zone",
            comments=merge_nsm_config_document_into_comments("", {"menu": "objects"}),
        )
        with patch(
            "netbox_nsm.objects.cot_routes._custom_object_type_model"
        ) as model_accessor:
            model_accessor.return_value.objects.filter.return_value.first.return_value = (
                cot
            )
            self.assertTrue(is_nsm_object_menu_slug("nsm_zone"))

    def test_other_menu_slug_is_not_menu_slug(self):
        cot = SimpleNamespace(
            slug="nsm_object_link",
            comments=merge_nsm_config_document_into_comments("", {"menu": "links"}),
        )
        with patch(
            "netbox_nsm.objects.cot_routes._custom_object_type_model"
        ) as model_accessor:
            model_accessor.return_value.objects.filter.return_value.first.return_value = (
                cot
            )
            self.assertFalse(is_nsm_object_menu_slug("nsm_object_link"))

    def test_cot_belongs_to_nsm_objects_menu(self):
        self.assertTrue(
            cot_belongs_to_nsm_objects_menu(
                SimpleNamespace(
                    slug="nsm_zone",
                    comments=merge_nsm_config_document_into_comments(
                        "", {"menu": "objects"}
                    ),
                )
            )
        )
        self.assertFalse(
            cot_belongs_to_nsm_objects_menu(
                SimpleNamespace(
                    slug="nsm_object_link",
                    comments=merge_nsm_config_document_into_comments(
                        "", {"menu": "links"}
                    ),
                )
            )
        )


class CotRoutePatchTests(SimpleTestCase):
    def test_apply_co_view_patches_marks_dispatch(self):
        try:
            from netbox_custom_objects.views import CustomObjectView
        except ImportError:
            self.skipTest("netbox-custom-objects not installed")

        self.assertTrue(
            getattr(CustomObjectView.dispatch, "_nsm_co_view_patch", False),
            "Plugin ready() should patch CustomObjectView for NSM objects menu",
        )

    @patch("netbox_nsm.objects.cot_routes.nsm_object_reverse", return_value="/nsm/zone/1/")
    @patch("netbox_nsm.objects.cot_routes._should_use_nsm_object_urls", return_value=True)
    def test_url_patch_routes_absolute_url_to_nsm(self, _mock_should, _mock_reverse):
        try:
            from netbox_custom_objects.models import CustomObject
        except ImportError:
            self.skipTest("netbox-custom-objects not installed")

        if not hasattr(CustomObject.get_absolute_url, "__wrapped__"):
            apply_nsm_object_url_patches()

        class _Obj:
            pk = 1
            custom_object_type = SimpleNamespace(slug="nsm_zone")

        self.assertEqual(CustomObject.get_absolute_url(_Obj()), "/nsm/zone/1/")

    @patch("netbox_nsm.objects.cot_routes.nsm_object_reverse", return_value="/nsm/zone/1/security/")
    @patch("netbox_nsm.objects.cot_routes._should_use_nsm_object_urls", return_value=True)
    def test_url_patch_routes_security_action_to_nsm(self, _mock_should, mock_reverse):
        try:
            from netbox_custom_objects.models import CustomObject
        except ImportError:
            self.skipTest("netbox-custom-objects not installed")

        if not hasattr(CustomObject.get_absolute_url, "__wrapped__"):
            apply_nsm_object_url_patches()

        class _Cls:
            custom_object_type = SimpleNamespace(slug="nsm_zone")

        url = CustomObject._get_action_url(_Cls, action="security", kwargs={"pk": 1})
        self.assertEqual(url, "/nsm/zone/1/security/")
        mock_reverse.assert_called_once_with("security", "nsm_zone", pk=1)
