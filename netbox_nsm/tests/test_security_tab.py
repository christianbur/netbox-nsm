"""Tests for the Security detail tab (replaces the right panel)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Site
from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase
from django.urls import reverse
from netbox.registry import registry

from netbox_nsm.security.tab.badge import count_security_tab_badge
from netbox_nsm.security.tab.registry import register_security_tabs
from netbox_nsm.security.tab.security_views import (
    _CO_BASE_TEMPLATE,
    _NSM_CO_BASE_TEMPLATE,
    SECURITY_TAB_PATH,
    _get_base_template,
    make_security_tab_view,
    register_security_tab_on_model,
)
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

    def test_security_not_in_hardcoded_tab_names(self):
        from netbox_nsm.templatetags.nsm_security_tab_tags import (
            _HARDCODED_TAB_NAMES,
        )

        self.assertNotIn("security", _HARDCODED_TAB_NAMES)

    @patch("netbox_nsm.templatetags.nsm_security_tab_tags._get_tab_action_url")
    def test_co_security_tab_via_plugin_extra_tabs_when_badge_is_zero(
        self, mock_get_tab_action_url
    ):
        from django.test import RequestFactory

        from netbox_nsm.security.tab.security_views import make_co_security_view
        from netbox_nsm.templatetags.nsm_security_tab_tags import nsm_plugin_extra_tabs

        co_view = make_co_security_view()
        co_view.tab.render = lambda _instance: {
            "label": "Security",
            "badge": 0,
            "weight": 1500,
        }
        instance = MagicMock()
        instance._meta.app_label = "netbox_custom_objects"
        instance._meta.model_name = "table7model"
        instance.pk = 1
        instance.custom_object_type = MagicMock(slug="nsm_zone")

        security_url = "/plugins/netbox-nsm/objects/nsm_zone/1/security/"
        mock_get_tab_action_url.return_value = security_url
        request = RequestFactory().get("/plugins/netbox-nsm/objects/nsm_zone/1/")
        request.user = MagicMock(has_perm=lambda *_args, **_kwargs: True)

        with patch.dict(
            registry["views"],
            {
                "netbox_custom_objects": {
                    "customobject": [
                        {"name": "security", "view": co_view},
                    ]
                }
            },
            clear=False,
        ):
            result = nsm_plugin_extra_tabs({"request": request, "tab": None}, instance)

        self.assertEqual(len(result["tabs"]), 1)
        self.assertEqual(result["tabs"][0]["url"], security_url)
        self.assertEqual(result["tabs"][0]["name"], "security")
        self.assertFalse(result["tabs"][0]["is_active"])
        mock_get_tab_action_url.assert_called_once_with(
            instance,
            action="security",
            kwargs={"pk": 1},
        )

        active_request = RequestFactory().get(security_url)
        active_request.user = request.user
        with patch.dict(
            registry["views"],
            {
                "netbox_custom_objects": {
                    "customobject": [
                        {"name": "security", "view": co_view},
                    ]
                }
            },
            clear=False,
        ):
            active_result = nsm_plugin_extra_tabs(
                {"request": active_request, "tab": None},
                instance,
            )
        self.assertTrue(active_result["tabs"][0]["is_active"])

    def test_registry_model_name_maps_dynamic_co_models_to_customobject(self):
        from netbox_nsm.templatetags.nsm_security_tab_tags import _registry_model_name

        instance = MagicMock()
        instance._meta.app_label = "netbox_custom_objects"
        instance._meta.model_name = "table7model"
        self.assertEqual(_registry_model_name(instance), "customobject")

        device = MagicMock()
        device._meta.app_label = "dcim"
        device._meta.model_name = "device"
        self.assertEqual(_registry_model_name(device), "device")

    @patch("netbox_nsm.templatetags.nsm_security_tab_tags.reverse")
    def test_get_tab_action_url_uses_patched_get_viewname_for_custom_objects(
        self, mock_reverse
    ):
        from netbox_nsm.templatetags.nsm_security_tab_tags import _get_tab_action_url

        instance = MagicMock()
        instance._meta.app_label = "netbox_custom_objects"
        instance.pk = 23
        instance.custom_object_type = MagicMock(slug="nsm_zone")

        with patch(
            "netbox_custom_objects.utilities.get_viewname",
            return_value="plugins:netbox_nsm:nsm_object_security",
        ):
            mock_reverse.return_value = (
                "/plugins/netbox-nsm/objects/nsm_zone/23/security/"
            )
            url = _get_tab_action_url(
                instance,
                action="security",
                kwargs={"pk": 23},
            )

        self.assertEqual(url, "/plugins/netbox-nsm/objects/nsm_zone/23/security/")
        mock_reverse.assert_called_once_with(
            "plugins:netbox_nsm:nsm_object_security",
            kwargs={"pk": 23, "custom_object_type": "nsm_zone"},
        )


class SecurityTabBaseTemplateTests(SimpleTestCase):
    """Regression: the Security tab must keep the Security nav-link visible.

    For NSM-scoped custom objects the Security tab nav-link is rendered by
    ``nsm_plugin_extra_tabs`` on ``netbox_nsm/customobject.html``. If the Security
    tab view extends the upstream CO template instead, that template's tabs block
    has no Security tab, so clicking the tab makes it (and the active highlight)
    vanish. The view must extend the NSM template — the same base used by
    ``NsmCustomObjectJournalView`` / ``…ChangeLogView``.
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
            "netbox_nsm.security.tab.security_views.get_default_template",
            return_value="dcim/device.html",
        ) as mock_default:
            self.assertEqual(_get_base_template(instance), "dcim/device.html")
        mock_default.assert_called_once_with(instance)


class SecurityTabRegistryTests(TestCase):
    def test_nsm_object_security_url_declared_statically(self):
        import netbox_nsm.urls as nsm_urls

        names = {
            p.name for p in nsm_urls.urlpatterns if hasattr(p, "name") and p.name
        }
        self.assertIn("nsm_object_security", names)

    def test_security_tab_registered_on_device(self):
        views = registry["views"]["dcim"]["device"]
        self.assertTrue(
            any(entry["name"] == SECURITY_TAB_PATH for entry in views),
            "Security tab should be registered on Device during plugin ready()",
        )

    def test_security_tab_registered_on_custom_object(self):
        try:
            from netbox_custom_objects.models import CustomObject
        except ImportError:
            self.skipTest("netbox-custom-objects not installed")

        views = registry["views"]["netbox_custom_objects"]["customobject"]
        security_entries = [
            entry for entry in views if entry["name"] == SECURITY_TAB_PATH
        ]
        self.assertEqual(len(security_entries), 1)
        view = security_entries[0]["view"]
        if isinstance(view, str):
            from django.utils.module_loading import import_string

            view = import_string(view)
        self.assertEqual(view.__name__, "_COSecurityTabView")

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
    @patch("netbox_nsm.security.tab.badge._count_enforcement_entries", return_value=0)
    @patch("netbox_nsm.security.tab.badge._count_interface_analysis_entries", return_value=0)
    @patch(
        "netbox_nsm.security.tab.badge.count_security_link_table_rows",
        return_value=3,
    )
    def test_badge_sums_link_table_and_panel_counts(self, *_mocks):
        device = Device(name="edge-1")
        device.pk = 1
        self.assertEqual(count_security_tab_badge(device), 3)

    def test_badge_zero_without_pk(self):
        device = Device(name="edge-1")
        self.assertEqual(count_security_tab_badge(device), 0)

    @patch(
        "netbox_nsm.security.tab.context.build_cot_security_rulebook_groups",
        return_value={"rulebook_groups": [], "unique_rules_total": 5},
    )
    @patch("netbox_nsm.security.tab.context.append_cot_reference_link_groups")
    @patch("netbox_nsm.security.tab.context.get_display_template_map", return_value={})
    @patch("netbox_nsm.security.tab.context.ContentType")
    @patch("netbox_nsm.security.tab.context.count_security_tab_badge", return_value=2)
    def test_context_badge_uses_tab_badge_not_rulebook_total(
        self,
        mock_badge,
        mock_ct,
        _mock_tmpl,
        mock_append,
        _mock_rulebooks,
    ):
        from django.test import RequestFactory

        from netbox_nsm.security.tab.context import build_security_tab_context

        mock_append.return_value = None
        mock_ct.objects.get_for_model.return_value = MagicMock(pk=1)
        obj = MagicMock(pk=111)
        ctx = build_security_tab_context(
            obj,
            RequestFactory().get("/ipam/prefixes/111/security/"),
        )
        mock_badge.assert_called_once_with(obj)
        self.assertEqual(ctx["nsm_security_badge"], 2)
        self.assertEqual(ctx["nsm_unique_rules_total"], 5)


class SecurityTabBadgeLinkTableCountTests(SimpleTestCase):
    """Badge counter must match deduped Security link-table rows."""

    def test_ipam_fk_skipped_when_same_url_already_in_cot_rows(self):
        from netbox_nsm.security.tab.security_rows import (
            _count_ipam_fk_security_rows,
            count_security_link_table_rows,
        )

        addr_url = "/plugins/netbox-nsm/objects/nsm_address/36/"
        addr = SimpleNamespace(pk=36, get_absolute_url=lambda: addr_url)
        host = SimpleNamespace(pk=111)

        with patch(
            "netbox_nsm.security.tab.security_rows._iter_deduped_cot_reference_rows",
            return_value=[(addr, SimpleNamespace())],
        ), patch(
            "netbox_nsm.security.tab.security_rows._count_ipam_fk_security_rows",
            wraps=_count_ipam_fk_security_rows,
        ) as mock_ipam, patch(
            "netbox_nsm.security.tab.security_rows._count_group_m2m_security_rows",
            return_value=0,
        ):
            self.assertEqual(count_security_link_table_rows(host), 1)
            mock_ipam.assert_called_once()
            existing_urls = mock_ipam.call_args.args[1]
            self.assertIn(addr_url, existing_urls)

    def test_count_ipam_fk_security_rows_skips_existing_urls(self):
        from netbox_nsm.security.tab.security_rows import _count_ipam_fk_security_rows

        addr_url = "/plugins/netbox-nsm/objects/nsm_address/36/"
        addr = SimpleNamespace(pk=36, get_absolute_url=lambda: addr_url)
        prefix = SimpleNamespace(pk=111)
        ipam_types = (type(prefix), type(prefix), type(prefix))

        with patch(
            "netbox_nsm.addresses.address_ipam_fk.get_nsm_address_model",
            return_value=object(),
        ), patch(
            "netbox_nsm.addresses.address_ipam_fk.iter_addresses_for_ipam_object",
            return_value=[(addr, "address")],
        ), patch(
            "netbox_nsm.addresses.address_ipam_fk.is_nsm_address_object",
            return_value=False,
        ), patch("ipam.models.IPAddress", ipam_types[0]), patch(
            "ipam.models.Prefix", ipam_types[1]
        ), patch("ipam.models.IPRange", ipam_types[2]):
            existing = {addr_url}
            self.assertEqual(_count_ipam_fk_security_rows(prefix, existing), 0)
            self.assertEqual(len(existing), 1)

    def test_count_cot_reference_links_skips_untransformed_junction_rows(self):
        from netbox_nsm.security.tab.security_rows import count_cot_reference_links

        rows = [
            (SimpleNamespace(pk=1), SimpleNamespace()),
            (SimpleNamespace(pk=2), SimpleNamespace()),
        ]
        with patch(
            "netbox_nsm.security.tab.security_rows._get_linked_custom_objects",
            return_value=rows,
        ), patch(
            "netbox_nsm.security.tab.security_rows.is_untransformed_junction_row",
            side_effect=[True, False],
        ), patch(
            "netbox_nsm.security.tab.security_rows._row_type_key",
            return_value=("co__zone", SimpleNamespace(pk=1)),
        ):
            self.assertEqual(count_cot_reference_links(SimpleNamespace(pk=1)), 1)


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

    @patch("netbox_nsm.security.tab.security_views.build_security_tab_context")
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


class SecurityTabExtensionTests(TestCase):
    def test_legacy_security_panel_extension_removed(self):
        from netbox_nsm import template_content

        names = [ext.__name__ for ext in template_content.template_extensions]
        self.assertNotIn("NsmSecurityLinksExtension", names)
