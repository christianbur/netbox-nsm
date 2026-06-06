"""HTTP integration tests for the zone matrix grid API."""

import json

from django.test import RequestFactory
from django.urls import reverse

from netbox_nsm.models import Rulebook, RulebookTypeChoices
from netbox_nsm.views.matrix_grid_api import RulebookMatrixGridApiView
from utilities.testing import TestCase


class MatrixGridApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="Matrix API RB",
            rulebook_type=RulebookTypeChoices.SECURITY_RULES,
        )
        cls.other_rulebook = Rulebook.objects.create(
            name="Matrix API Other",
            rulebook_type="other",
        )

    def test_scaffold_returns_column_defs(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = (
            reverse(
                "plugins:netbox_nsm:rulebook_matrix_grid_api",
                args=[self.rulebook.pk],
            )
            + "?scaffold=1&mode=undirected"
        )
        request = RequestFactory().get(url)
        request.user = self.user
        response = RulebookMatrixGridApiView.as_view()(request, pk=self.rulebook.pk)
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)
        self.assertIn("columnDefs", data)
        self.assertIn("gridMeta", data)

    def test_page_request_returns_row_data(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = (
            reverse(
                "plugins:netbox_nsm:rulebook_matrix_grid_api",
                args=[self.rulebook.pk],
            )
            + "?startRow=0&endRow=50&mode=undirected"
        )
        request = RequestFactory().get(url)
        request.user = self.user
        response = RulebookMatrixGridApiView.as_view()(request, pk=self.rulebook.pk)
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)
        self.assertIn("rowData", data)

    def test_directed_mode_accepted(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = (
            reverse(
                "plugins:netbox_nsm:rulebook_matrix_grid_api",
                args=[self.rulebook.pk],
            )
            + "?scaffold=1&mode=directed"
        )
        request = RequestFactory().get(url)
        request.user = self.user
        response = RulebookMatrixGridApiView.as_view()(request, pk=self.rulebook.pk)
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)
        self.assertEqual(data["matrixMode"], "directed")

    def test_non_security_rulebook_returns_404(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse(
            "plugins:netbox_nsm:rulebook_matrix_grid_api",
            args=[self.other_rulebook.pk],
        )
        request = RequestFactory().get(url)
        request.user = self.user
        response = RulebookMatrixGridApiView.as_view()(
            request, pk=self.other_rulebook.pk
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_forbidden_without_permission(self):
        url = reverse(
            "plugins:netbox_nsm:rulebook_matrix_grid_api",
            args=[self.rulebook.pk],
        )
        request = RequestFactory().get(url)
        request.user = self.user
        response = RulebookMatrixGridApiView.as_view()(request, pk=self.rulebook.pk)
        self.assertEqual(response.status_code, 403, response.content)
