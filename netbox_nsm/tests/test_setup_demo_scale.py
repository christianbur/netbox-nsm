"""Setup wizard: scale demo guards and RQ import paths."""

from unittest import mock

from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from netbox_nsm.views.setup import demo
from netbox_nsm.views.setup.view import SetupView

_SETUP_PLUGINS_CONFIG = {
    "netbox_nsm": {
        "setup_menu": True,
        "setup_allow_destructive_actions": True,
    },
    "netbox_branching": {},
}


def _setup_post_request(data):
    request = RequestFactory().post("/plugins/netbox-nsm/setup/", data)
    request.user = mock.Mock(is_authenticated=True)
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


class SetupDemoScaleTests(SimpleTestCase):
    def test_starter_demo_grid_dimensions(self):
        self.assertEqual(demo.DEMO_GRID_SIZE, 250)
        self.assertEqual(demo.DEMO_ZONE_COUNT, 250)
        self.assertEqual(demo.DEMO_RULE_COUNT, 62_500)
        self.assertEqual(demo._demo_zone_name(0), "zone_001")
        self.assertEqual(demo._demo_zone_name(249), "zone_250")
        self.assertEqual(demo._matrix_indices(0), (0, 0))
        self.assertEqual(demo._matrix_indices(249), (0, 249))
        self.assertEqual(demo._matrix_indices(250), (1, 0))
        self.assertEqual(demo._matrix_indices(demo.DEMO_RULE_COUNT - 1), (249, 249))

    def test_scale_demo_import_path(self):
        self.assertEqual(
            demo.SCALE_DEMO_50K_IMPORT,
            "netbox_nsm.demos.addresses_million_scale.create_addresses_scale_demo_50k",
        )

    @mock.patch.object(demo, "redirect")
    @mock.patch.object(demo, "_queue_demo_import", return_value=True)
    @mock.patch.object(demo.IPAddress.objects, "exists", return_value=True)
    def test_scale_50k_queues_rq_job_even_when_ipam_has_addresses(
        self, _mock_exists, mock_queue, mock_redirect
    ):
        request = RequestFactory().post("/plugins/netbox-nsm/setup/")
        demo.handle_demo_action(request, "create_demo_scale_50k")
        mock_queue.assert_called_once()
        self.assertEqual(
            mock_queue.call_args.kwargs["import_path"],
            demo.SCALE_DEMO_50K_IMPORT,
        )
        mock_redirect.assert_called_once_with(reverse("plugins:netbox_nsm:setup"))

    @override_settings(PLUGINS_CONFIG=_SETUP_PLUGINS_CONFIG)
    @mock.patch.object(demo, "handle_demo_action")
    @mock.patch(
        "netbox_nsm.views.setup.view.custom_objects.custom_objects_db_ready",
        return_value=True,
    )
    @mock.patch.object(SetupView, "_build_context")
    def test_scale_50k_post_requires_confirm_checkbox(
        self, mock_build_context, _mock_db_ready, mock_handle_demo
    ):
        mock_build_context.return_value = {
            "can_import_cots": False,
            "can_create_typeconfigs": False,
            "all_cots_ok": True,
            "all_tcs_ok": True,
            "custom_objects_db_ready": True,
        }
        request = _setup_post_request({"action": "create_demo_scale_50k"})
        response = SetupView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        mock_handle_demo.assert_not_called()
        msgs = [str(m) for m in get_messages(request)]
        self.assertTrue(any("confirm" in m.lower() for m in msgs))

    @override_settings(PLUGINS_CONFIG=_SETUP_PLUGINS_CONFIG)
    @mock.patch.object(demo, "handle_demo_action")
    @mock.patch(
        "netbox_nsm.views.setup.view.custom_objects.custom_objects_db_ready",
        return_value=True,
    )
    @mock.patch.object(SetupView, "_build_context")
    def test_scale_50k_post_with_confirm_delegates_to_demo_handler(
        self, mock_build_context, _mock_db_ready, mock_handle_demo
    ):
        mock_build_context.return_value = {
            "can_import_cots": False,
            "can_create_typeconfigs": False,
            "all_cots_ok": True,
            "all_tcs_ok": True,
            "custom_objects_db_ready": True,
        }
        request = _setup_post_request(
            {
                "action": "create_demo_scale_50k",
                "scale_demo_50k_confirm": "1",
            }
        )
        SetupView.as_view()(request)
        mock_handle_demo.assert_called_once_with(request, "create_demo_scale_50k")
