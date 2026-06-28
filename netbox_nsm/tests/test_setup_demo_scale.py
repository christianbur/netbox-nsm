"""Setup wizard: scale demo guards and RQ import paths."""

from pathlib import Path
from unittest import mock

from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from netbox_nsm.import_ import demo
from netbox_nsm.import_.setup_view import SetupView

_SETUP_PLUGINS_CONFIG = {
    "netbox_nsm": {
        "setup_menu": True,
        "setup_allow_destructive_actions": True,
    },
    "netbox_branching": {},
}


def _setup_post_request(data):
    request = RequestFactory().post("/plugins/netbox-nsm/bundles/", data)
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
            "netbox_nsm.import_.demo_scale.create_addresses_scale_demo_50k",
        )

    @mock.patch.object(demo, "_queue_demo_import", return_value=True)
    def test_address_bundle_runpy_queues_rq_job(self, mock_queue):
        """Address bundle run.py always queues via RQ regardless of existing IP addresses."""
        request = RequestFactory().post("/plugins/netbox-nsm/bundles/")
        request.user = mock.Mock(is_authenticated=True)
        from netbox_nsm.bundles.builtin.nsm_demo_zone_address_adressgroup.run import main

        main(request)
        mock_queue.assert_called_once()
        self.assertEqual(
            mock_queue.call_args.kwargs["import_path"],
            demo.SCALE_DEMO_50K_IMPORT,
        )

    @override_settings(PLUGINS_CONFIG=_SETUP_PLUGINS_CONFIG)
    @mock.patch("netbox_nsm.bundles.runner.run_bundle")
    @mock.patch(
        "netbox_nsm.bundles.dispatch.load_bundle",
        return_value={
            "schema_type": "nsm",
            "schema_version": "1",
            "bundle_kind": "python",
            "needs_confirm": True,
            "confirm_label": "I confirm that IP addresses may be created in IPAM.",
        },
    )
    @mock.patch("netbox_nsm.bundles.paths.find_bundle_dirs")
    @mock.patch(
        "netbox_nsm.import_.custom_objects.custom_objects_db_ready",
        return_value=True,
    )
    def test_address_bundle_post_requires_confirm(
        self, _mock_db, mock_dirs, _mock_load, mock_run
    ):
        mock_dirs.return_value = {
            "nsm_demo_zone_address_adressgroup": Path("/fake/bundle")
        }
        request = _setup_post_request(
            {"action": "run_bundle", "slug": "nsm_demo_zone_address_adressgroup"}
        )
        response = SetupView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        mock_run.assert_not_called()
        msgs = [str(m) for m in get_messages(request)]
        self.assertTrue(any("confirm" in m.lower() for m in msgs))

    @override_settings(PLUGINS_CONFIG=_SETUP_PLUGINS_CONFIG)
    @mock.patch("netbox_nsm.bundles.runner.run_bundle")
    @mock.patch(
        "netbox_nsm.bundles.dispatch.load_bundle",
        return_value={
            "schema_type": "nsm",
            "schema_version": "1",
            "bundle_kind": "python",
            "needs_confirm": True,
            "confirm_label": "I confirm that IP addresses may be created in IPAM.",
        },
    )
    @mock.patch("netbox_nsm.bundles.paths.find_bundle_dirs")
    @mock.patch(
        "netbox_nsm.import_.custom_objects.custom_objects_db_ready",
        return_value=True,
    )
    def test_address_bundle_post_with_confirm_runs_bundle(
        self, _mock_db, mock_dirs, _mock_load, mock_run
    ):
        mock_dirs.return_value = {
            "nsm_demo_zone_address_adressgroup": Path("/fake/bundle")
        }
        request = _setup_post_request(
            {
                "action": "run_bundle",
                "slug": "nsm_demo_zone_address_adressgroup",
                "confirm": "1",
            }
        )
        SetupView.as_view()(request)
        mock_run.assert_called_once_with("nsm_demo_zone_address_adressgroup", request)
