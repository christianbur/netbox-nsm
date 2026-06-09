"""Setup wizard: scale demo guards and RQ import paths."""

from unittest import mock

from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from netbox_nsm.views.setup import demo


class SetupDemoScaleTests(SimpleTestCase):
    def test_scale_demo_import_path(self):
        self.assertEqual(
            demo.SCALE_DEMO_50K_IMPORT,
            "netbox_nsm.demos.addresses_million_scale.create_addresses_scale_demo_50k",
        )

    @mock.patch.object(demo, "redirect")
    @mock.patch.object(demo, "messages")
    @mock.patch.object(demo.IPAddress.objects, "exists", return_value=True)
    def test_scale_50k_rejected_when_ipam_has_addresses(
        self, _mock_exists, mock_messages, mock_redirect
    ):
        request = RequestFactory().post("/plugins/netbox-nsm/setup/")
        demo.handle_demo_action(request, "create_demo_scale_50k")
        mock_messages.error.assert_called_once()
        self.assertIn("IP address database", mock_messages.error.call_args[0][1])
        mock_redirect.assert_called_once_with(reverse("plugins:netbox_nsm:setup"))

    @mock.patch.object(demo, "redirect")
    @mock.patch.object(demo, "_queue_demo_import", return_value=True)
    @mock.patch.object(demo.IPAddress.objects, "exists", return_value=False)
    def test_scale_50k_queues_rq_job_when_ipam_empty(
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
