"""Tests for the Security detail tab (replaces the right panel)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Site
from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase
from django.urls import reverse
from netbox.registry import registry

from netbox_nsm.security.tab.badge import count_security_tab_badge
from netbox_nsm.security.tab.registry import register_security_tabs
from netbox_nsm.security.tab.views import (
    _CO_BASE_TEMPLATE,
    _NSM_CO_BASE_TEMPLATE,
    SECURITY_TAB_PATH,
    _get_base_template,
    make_security_tab_view,
    register_security_tab_on_model,
)
from netbox_nsm.template_content import NsmSecurityLinksExtension
from utilities.testing import TestCase

User = get_user_model()


class SecurityTabVisibilityTests(SimpleTestCase):
    def test_security_tab_visible_when_badge_is_zero(self):
        device = Device(name="edge-1")
        device.pk = 1
        view_class = make_security_tab_view(Device)
        view_class.tab.badge = lambda _obj: 0
        rendered = view_class.tab.render(device)
        self.assertIsNotNone(rendered)
        self.assertEqual(rendered["badge"], 0)

    @patch("netbox_nsm.templatetags.nsm_security_tab_tags.get_action_url")
    @patch("netbox_nsm.security.tab.badge.count_security_tab_badge", return_value=0)
    def test_co_security_tab_link_visible_when_badge_is_zero(
        self, _mock_badge, mock_get_action_url
    ):
        from django.test import RequestFactory

        from netbox_nsm.templatetags.nsm_security_tab_tags import nsm_security_tab_link

        device = Device(name="edge-1")
        device.pk = 1
        mock_get_action_url.return_value = "/dcim/devices/1/security/"
        request = RequestFactory().get("/dcim/devices/1/")
        result = nsm_security_tab_link(
            {"request": request},
            device,
        )
        self.assertIsNotNone(result["tab"])
        self.assertEqual(result["tab"]["url"], "/dcim/devices/1/security/")
        self.assertIsNone(result["tab"]["badge"])


class SecurityTabBaseTemplateTests(SimpleTestCase):
    """Regression: the Security tab must keep the Security nav-link visible.

    For NSM-scoped custom objects the Security tab nav-link only exists in the
    NSM detail template (``netbox_nsm/customobject.html`` → ``nsm_security_tab_link``).
    If the Security tab view extends the *upstream* CO template instead, that
    template's tabs block has no Security tab, so clicking the tab makes it (and
    the active highlight) vanish. The view must extend the NSM template — the
    same base used by ``NsmCustomObjectJournalView`` / ``…ChangeLogView``.
    """

    def _co_instance(self, slug="action"):
        instance = MagicMock()
        instance._meta.app_label = "netbox_custom_objects"
        instance.custom_object_type.slug = slug
        return instance

    @patch(
        "netbox_nsm.objects.cot_routes.is_nsm_object_menu_slug", return_value=True
    )
    def test_nsm_custom_object_uses_nsm_base_template(self, _mock_is_nsm):
        self.assertEqual(
            _get_base_template(self._co_instance()), _NSM_CO_BASE_TEMPLATE
        )
        self.assertEqual(_NSM_CO_BASE_TEMPLATE, "netbox_nsm/customobject.html")

    @patch(
        "netbox_nsm.objects.cot_routes.is_nsm_object_menu_slug", return_value=False
    )
    def test_generic_custom_object_uses_upstream_base_template(self, _mock_is_nsm):
        self.assertEqual(_get_base_template(self._co_instance()), _CO_BASE_TEMPLATE)

    def test_builtin_model_uses_default_template(self):
        instance = MagicMock()
        instance._meta.app_label = "dcim"
        with patch(
            "netbox_nsm.security.tab.views.get_default_template",
            return_value="dcim/device.html",
        ) as mock_default:
            self.assertEqual(_get_base_template(instance), "dcim/device.html")
        mock_default.assert_called_once_with(instance)


class SecurityTabRegistryTests(TestCase):
    def test_security_tab_registered_on_device(self):
        views = registry["views"]["dcim"]["device"]
        self.assertTrue(
            any(entry["name"] == SECURITY_TAB_PATH for entry in views),
            "Security tab should be registered on Device during plugin ready()",
        )

    def test_register_security_tab_on_model_is_idempotent(self):
        self.assertFalse(register_security_tab_on_model(Device))

    @patch("netbox_nsm.security.tab.registry._public_host_model_classes", return_value=[])
    @patch("netbox_nsm.security.tab.registry._inject_co_security_url")
    @patch("netbox_nsm.security.tab.registry._inject_nsm_object_security_url")
    @patch("netbox_nsm.security.tab.registry._register_custom_object_security_tab")
    @patch("netbox_nsm.security.tab.registry.clear_url_caches")
    def test_register_security_tabs_clears_url_cache(
        self,
        mock_clear,
        mock_register_co,
        mock_inject_nsm,
        mock_inject_co,
        _mock_models,
    ):
        register_security_tabs()
        mock_inject_co.assert_called_once()
        mock_inject_nsm.assert_called_once()
        mock_register_co.assert_called_once()
        mock_clear.assert_called_once()


class SecurityTabBadgeTests(TestCase):
    @patch("netbox_nsm.security.tab.badge.build_cot_security_panel_groups")
    @patch("netbox_nsm.security.tab.badge._count_object_links", return_value=0)
    @patch("netbox_nsm.security.tab.badge._count_extra_link_refs", return_value=0)
    @patch("netbox_nsm.security.tab.badge._count_enforcement_entries", return_value=0)
    @patch("netbox_nsm.security.tab.badge._count_interface_analysis_entries", return_value=0)
    def test_badge_sums_rule_and_link_counts(self, *_mocks):
        device = Device(name="edge-1")
        device.pk = 1
        with patch(
            "netbox_nsm.security.tab.badge.ContentType.objects.get_for_model",
            return_value=MagicMock(pk=10),
        ):
            with patch(
                "netbox_nsm.security.tab.badge.build_cot_security_panel_groups",
                return_value={"unique_rules_total": 3},
            ):
                self.assertEqual(count_security_tab_badge(device), 3)

    def test_badge_zero_without_pk(self):
        device = Device(name="edge-1")
        self.assertEqual(count_security_tab_badge(device), 0)


class SecurityTabViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="security-tab-user",
            password="password",
        )
        site, _ = Site.objects.get_or_create(
            name="Security Tab Test Site",
            defaults={"slug": "security-tab-test-site", "status": "active"},
        )
        manufacturer, _ = Manufacturer.objects.get_or_create(
            name="Security Tab Test Mfr",
            defaults={"slug": "security-tab-test-mfr"},
        )
        device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model="Security Tab Test Model",
            defaults={"slug": "security-tab-test-model"},
        )
        role, _ = DeviceRole.objects.get_or_create(
            name="Security Tab Test Role",
            defaults={"slug": "security-tab-test-role"},
        )
        cls.device, _ = Device.objects.get_or_create(
            name="security-tab-device",
            defaults={
                "device_type": device_type,
                "role": role,
                "site": site,
                "status": "active",
            },
        )

    def setUp(self):
        self.client = Client()

    @patch("netbox_nsm.security.tab.views.build_security_tab_context")
    def test_device_security_tab_renders(self, mock_context):
        mock_context.return_value = {
            "nsm_link_type_groups": [],
            "nsm_rulebook_groups": [],
            "nsm_assign_url": "/assign/",
            "nsm_analyzer_url": "/analyzer/",
            "nsm_panel_label": "Security",
            "nsm_page_addr_analyzable": False,
        }
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("dcim:device_security", kwargs={"pk": self.device.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "netbox_nsm/security_tab.html")

    def test_device_security_tab_requires_login_when_login_required(self):
        from django.conf import settings

        if not settings.LOGIN_REQUIRED:
            self.skipTest("LOGIN_REQUIRED is disabled")
        response = self.client.get(
            reverse("dcim:device_security", kwargs={"pk": self.device.pk})
        )
        self.assertEqual(response.status_code, 302)


class SecurityPanelDisabledTests(TestCase):
    def test_right_page_is_empty(self):
        extension = NsmSecurityLinksExtension(None)
        self.assertEqual(extension.right_page(), "")
