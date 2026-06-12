"""Background demo import queue helpers."""

from unittest import mock

from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.views.setup import demo

SCALE_IMPORT = "netbox_nsm.demos.scale_test.create_scale_test_demo"


class DemoQueueTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().post("/plugins/netbox-nsm/setup/")

    @mock.patch.object(demo, "messages")
    @mock.patch.object(demo, "_count_active_rq_workers", return_value=0)
    def test_queue_demo_import_errors_without_worker(
        self, _mock_workers, mock_messages
    ):
        ok = demo._queue_demo_import(
            self.request,
            import_path=SCALE_IMPORT,
            label="Scale test",
            rulebook_name="Demo - Scale Test",
        )
        self.assertFalse(ok)
        mock_messages.error.assert_called_once()
        self.assertIn("no RQ worker", mock_messages.error.call_args[0][1])

    @mock.patch.object(demo, "messages")
    @mock.patch.object(demo, "_find_pending_demo_job")
    @mock.patch.object(demo, "_count_active_rq_workers", return_value=1)
    def test_queue_demo_import_reports_existing_pending_job(
        self, _mock_workers, mock_pending, mock_messages
    ):
        pending = mock.Mock(id="abc-123")
        mock_pending.return_value = pending
        ok = demo._queue_demo_import(
            self.request,
            import_path=SCALE_IMPORT,
            label="Scale test",
            rulebook_name="Demo - Scale Test",
        )
        self.assertTrue(ok)
        mock_messages.info.assert_called_once()
        body = mock_messages.info.call_args[0][1]
        self.assertIn("already queued or running", body)
        self.assertIn("abc-123", body)

    @mock.patch.object(demo, "get_nsm_menu_label", return_value="Firewall")
    @mock.patch.object(demo, "messages")
    @mock.patch("django_rq.get_queue")
    @mock.patch.object(demo, "_find_pending_demo_job", return_value=None)
    @mock.patch.object(demo, "_count_active_rq_workers", return_value=1)
    def test_queue_demo_import_mentions_backlog(
        self, _mock_workers, _mock_pending, mock_get_queue, mock_messages, _mock_menu
    ):
        queue = mock.Mock()
        queue.job_ids = ["job-a", "job-b"]
        job = mock.Mock(id="new-job-id")
        queue.enqueue.return_value = job
        mock_get_queue.return_value = queue

        ok = demo._queue_demo_import(
            self.request,
            import_path=SCALE_IMPORT,
            label="Scale test",
            rulebook_name="Demo - Scale Test",
        )
        self.assertTrue(ok)
        mock_messages.success.assert_called_once()
        body = mock_messages.success.call_args[0][1]
        self.assertIn("1 other job(s)", body)
        self.assertIn("Firewall → Rulebooks", body)
        queue.enqueue.assert_called_once()
