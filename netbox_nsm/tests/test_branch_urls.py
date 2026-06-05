"""Tests for netbox_branching URL helpers."""

from unittest.mock import patch

from django.test import SimpleTestCase, RequestFactory

from netbox_nsm.branch_urls import (
    branch_schema_id_from_request,
    with_branch_query,
    wrap_matrix_cell_hrefs,
    wrap_policy_row_urls,
)


class BranchUrlTests(SimpleTestCase):
    def test_without_branch_cookie_url_unchanged(self):
        request = RequestFactory().get("/")
        self.assertIsNone(branch_schema_id_from_request(request))
        self.assertEqual(
            with_branch_query("/plugins/netbox-nsm/rules/1/", request),
            "/plugins/netbox-nsm/rules/1/",
        )

    @patch("netbox_branching.constants.COOKIE_NAME", "active_branch")
    @patch("netbox_branching.constants.QUERY_PARAM", "_branch")
    def test_with_branch_cookie_appends_query(self):
        request = RequestFactory().get("/")
        request.COOKIES = {"active_branch": "abc12345"}
        self.assertEqual(branch_schema_id_from_request(request), "abc12345")
        self.assertEqual(
            with_branch_query("/plugins/netbox-nsm/rules/1/", request),
            "/plugins/netbox-nsm/rules/1/?_branch=abc12345",
        )
        self.assertEqual(
            with_branch_query("/path?nsm_q=foo", request),
            "/path?nsm_q=foo&_branch=abc12345",
        )

    @patch("netbox_branching.constants.COOKIE_NAME", "active_branch")
    @patch("netbox_branching.constants.QUERY_PARAM", "_branch")
    def test_wrap_policy_and_matrix_urls(self):
        request = RequestFactory().get("/")
        request.COOKIES = {"active_branch": "hh123456"}
        rows = [
            {
                "url": "/rules/1/",
                "edit_url": "/rules/1/edit/",
                "delete_url": "/rules/1/delete/",
                "system": {"url": "/rules/1/"},
            }
        ]
        wrap_policy_row_urls(rows, request)
        self.assertIn("_branch=hh123456", rows[0]["edit_url"])

        cells = [{"fwd_href": "/rules/?nsm_q=a", "add_href": "/rules/add/"}]
        wrap_matrix_cell_hrefs(cells, request)
        self.assertIn("_branch=hh123456", cells[0]["fwd_href"])
