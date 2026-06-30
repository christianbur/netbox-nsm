"""COT rulebook Matrix tab — visibility, URL, and context."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from netbox_nsm.tests.rulebook_permission_helpers import grant_rulebook_cot_perms
from utilities.testing import TestCase

from netbox_nsm.matrix.cot_matrix_tab_context import (
    cot_rulebook_matrix_capable,
    cot_rulebook_matrix_enabled,
)
from netbox_nsm.type_metadata.rulebook import (
    resolve_rulebook_config_for_cot,
    save_rulebook_config_for_cot,
)
from netbox_nsm.rulebooks.cot_hierarchy import get_cot_matrix_tab_enabled
from netbox_nsm.rulebooks.templates import RULEBOOK_GROUP
from netbox_nsm.rulebooks.virtual_cot import VirtualCotRulebook
from netbox_nsm.rulebooks.virtual_cot_tabs import build_virtual_cot_rulebook_tabs


def _cot_with_fields(*field_names: str):
    fields = MagicMock()
    fields.values_list.return_value = field_names
    cot = SimpleNamespace(
        fields=fields,
        slug="nsm_rb_test01",
        pk=10,
        name="test01",
        verbose_name="Test 01",
        description="",
    )
    return cot


class CotRulebookMatrixCapableTests(SimpleTestCase):
    def test_capable_when_both_zone_fields_present(self):
        cot = _cot_with_fields("index", "source_zones", "destination_zones", "actions")
        self.assertTrue(cot_rulebook_matrix_capable(cot))

    def test_capable_when_generic_source_destination_present(self):
        cot = _cot_with_fields("index", "source", "destination", "actions")
        self.assertTrue(cot_rulebook_matrix_capable(cot))

    def test_not_capable_without_source_zones(self):
        cot = _cot_with_fields("index", "destination_zones", "actions")
        self.assertFalse(cot_rulebook_matrix_capable(cot))

    def test_not_capable_without_destination_zones(self):
        cot = _cot_with_fields("index", "source_zones", "actions")
        self.assertFalse(cot_rulebook_matrix_capable(cot))


class CotRulebookMatrixEnabledTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from netbox_custom_objects.models import CustomObjectType

        cls.cot = CustomObjectType.objects.create(
            name="nsm_rb_test01",
            slug="nsm_rb_test01",
            verbose_name="Test 01",
            description="",
            group_name=RULEBOOK_GROUP,
        )

    def test_enabled_by_default_when_capable(self):
        cot = _cot_with_fields("source_zones", "destination_zones")
        self.assertTrue(cot_rulebook_matrix_enabled(cot))

    def test_disabled_when_matrix_tab_setting_false(self):
        save_rulebook_config_for_cot(self.cot, {"matrix_tab_enabled": False})
        cot = _cot_with_fields("source_zones", "destination_zones")
        cot.slug = self.cot.slug
        self.assertFalse(cot_rulebook_matrix_enabled(cot))

    def test_get_matrix_tab_enabled_defaults_true(self):
        self.assertTrue(get_cot_matrix_tab_enabled("nsm_rb_missing"))

    def test_set_matrix_tab_enabled_persists(self):
        save_rulebook_config_for_cot(self.cot, {"matrix_tab_enabled": False})
        self.cot.refresh_from_db()
        config = resolve_rulebook_config_for_cot(self.cot)
        self.assertFalse(config["matrix_tab_enabled"])
        self.assertFalse(get_cot_matrix_tab_enabled(self.cot.slug))


class CotVirtualRulebookTabsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from netbox_custom_objects.models import CustomObjectType

        cls.cot = CustomObjectType.objects.create(
            name="nsm_rb_test01",
            slug="nsm_rb_test01",
            verbose_name="Test 01",
            description="",
            group_name=RULEBOOK_GROUP,
        )

    def setUp(self):
        super().setUp()
        grant_rulebook_cot_perms(self, self.cot, view=True)
        self._can_view_patcher = patch(
            "netbox_nsm.rulebooks.virtual_cot_tabs.can_view_rulebook",
            return_value=True,
        )
        self._can_view_patcher.start()
        self.request = RequestFactory().get("/")
        self.request.user = self.user

    def tearDown(self):
        self._can_view_patcher.stop()
        super().tearDown()

    def test_matrix_tab_present_for_zone_rulebook(self):
        cot = _cot_with_fields("source_zones", "destination_zones")
        virtual = VirtualCotRulebook(cot, rule_count=2)
        tabs = build_virtual_cot_rulebook_tabs(self.request, virtual)
        keys = [tab["key"] for tab in tabs]
        self.assertIn("matrix", keys)
        matrix_tab = next(tab for tab in tabs if tab["key"] == "matrix")
        self.assertEqual(
            matrix_tab["url"],
            reverse(
                "plugins:netbox_nsm:cot_rulebook_matrix",
                kwargs={"slug": "nsm_rb_test01"},
            ),
        )

    def test_matrix_tab_absent_without_zone_fields(self):
        cot = _cot_with_fields("source_addresses", "destination_addresses")
        virtual = VirtualCotRulebook(cot, rule_count=1)
        tabs = build_virtual_cot_rulebook_tabs(self.request, virtual)
        self.assertNotIn("matrix", [tab["key"] for tab in tabs])

    def test_matrix_tab_absent_when_disabled(self):
        save_rulebook_config_for_cot(self.cot, {"matrix_tab_enabled": False})
        cot = _cot_with_fields("source_zones", "destination_zones")
        virtual = VirtualCotRulebook(cot, rule_count=2)
        tabs = build_virtual_cot_rulebook_tabs(self.request, virtual)
        self.assertNotIn("matrix", [tab["key"] for tab in tabs])

    def test_changelog_tab_present_after_matrix(self):
        self.add_permissions("core.view_objectchange")
        cot = _cot_with_fields("source_zones", "destination_zones")
        virtual = VirtualCotRulebook(cot, rule_count=2)
        tabs = build_virtual_cot_rulebook_tabs(self.request, virtual)
        keys = [tab["key"] for tab in tabs]
        self.assertIn("changelog", keys)
        self.assertLess(keys.index("matrix"), keys.index("changelog"))
        changelog_tab = next(tab for tab in tabs if tab["key"] == "changelog")
        self.assertEqual(
            changelog_tab["url"],
            reverse(
                "plugins:netbox_nsm:cot_rulebook_changelog",
                kwargs={"slug": "nsm_rb_test01"},
            ),
        )

    def test_changelog_tab_hidden_without_permission(self):
        request = RequestFactory().get("/")
        request.user = self.user
        cot = _cot_with_fields("source_zones", "destination_zones")
        virtual = VirtualCotRulebook(cot, rule_count=1)
        tabs = build_virtual_cot_rulebook_tabs(request, virtual)
        self.assertNotIn("changelog", [tab["key"] for tab in tabs])


class CotRulebookMatrixViewTests(SimpleTestCase):
    @patch("netbox_nsm.rulebooks.views.cot.can_view_rulebook", return_value=True)
    @patch("netbox_nsm.rulebooks.views.cot.get_deployed_cot_rulebook")
    @patch("netbox_nsm.rulebooks.views.cot.build_virtual_cot_rulebook_with_hierarchy")
    def test_matrix_view_returns_404_without_zone_fields(
        self, mock_build, mock_get_cot, _mock_can_view
    ):
        from django.http import Http404

        from netbox_nsm.rulebooks.views.cot import CotRulebookMatrixView

        cot = _cot_with_fields("source_addresses", "destination_addresses")
        mock_get_cot.return_value = cot
        mock_build.return_value = VirtualCotRulebook(cot, rule_count=0)

        request = RequestFactory().get("/")
        request.user = SimpleNamespace(
            is_authenticated=True,
            has_perm=lambda perm: True,
            has_perms=lambda perms: True,
        )
        with self.assertRaises(Http404):
            CotRulebookMatrixView.as_view()(request, slug="nsm_rb_addr")

    @patch("netbox_nsm.rulebooks.views.cot.can_view_rulebook", return_value=True)
    @patch("netbox_nsm.rulebooks.views.cot.get_deployed_cot_rulebook")
    @patch("netbox_nsm.rulebooks.views.cot.build_virtual_cot_rulebook_with_hierarchy")
    @patch("netbox_nsm.rulebooks.views.cot.cot_rulebook_matrix_enabled", return_value=False)
    def test_matrix_view_returns_404_when_tab_disabled(
        self, _mock_enabled, mock_build, mock_get_cot, _mock_can_view
    ):
        from django.http import Http404

        from netbox_nsm.rulebooks.views.cot import CotRulebookMatrixView

        cot = _cot_with_fields("source_zones", "destination_zones")
        mock_get_cot.return_value = cot
        virtual = MagicMock()
        virtual.cot = cot
        mock_build.return_value = virtual

        request = RequestFactory().get("/")
        request.user = SimpleNamespace(
            is_authenticated=True,
            has_perm=lambda perm: True,
            has_perms=lambda perms: True,
        )
        with self.assertRaises(Http404):
            CotRulebookMatrixView.as_view()(request, slug="nsm_rb_test01")


class MatrixObjectTypeSelectionTests(SimpleTestCase):
    def test_defaults_to_zone_when_present(self):
        from netbox_nsm.matrix.matrix_utils import resolve_matrix_object_type_selection

        raw_types = [
            {"ct_id": 256, "label": "Address"},
            {"ct_id": 259, "label": "Zone"},
        ]
        available_types = [
            {"ct_id": 256, "label": "Address"},
            {"ct_id": 259, "label": "Zone"},
        ]
        self.assertEqual(
            resolve_matrix_object_type_selection(
                None,
                raw_types=raw_types,
                available_types=available_types,
            ),
            259,
        )
