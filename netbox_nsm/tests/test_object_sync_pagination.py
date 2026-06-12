"""Tests for Object Sync list pagination."""

from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.views.object_sync_pagination import (
    OBJECT_SYNC_DEFAULT_PER_PAGE,
    paginate_sync_list,
    resolve_sync_per_page,
)


class ObjectSyncPaginationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_resolve_sync_per_page_defaults_to_25(self):
        request = self.factory.get("/plugins/netbox-nsm/object-sync/")
        self.assertEqual(
            resolve_sync_per_page(request, "sync_per_page"),
            OBJECT_SYNC_DEFAULT_PER_PAGE,
        )

    def test_resolve_sync_per_page_from_query(self):
        request = self.factory.get(
            "/plugins/netbox-nsm/object-sync/?sync_per_page=100"
        )
        self.assertEqual(resolve_sync_per_page(request, "sync_per_page"), 100)

    def test_paginate_sync_list_returns_page_slice(self):
        items = [SimpleNamespace(pk=i) for i in range(1, 31)]
        request = self.factory.get(
            "/plugins/netbox-nsm/object-sync/?sync_page=2&sync_per_page=10"
        )
        page_items, paginator, page_obj = paginate_sync_list(
            request,
            items,
            page_param="sync_page",
            per_page_param="sync_per_page",
        )
        self.assertEqual(paginator.count, 30)
        self.assertEqual(len(page_items), 10)
        self.assertEqual(page_obj.number, 2)
        self.assertEqual(page_items[0].pk, 11)

    def test_paginate_sync_list_clamps_invalid_page(self):
        request = self.factory.get("/plugins/netbox-nsm/object-sync/?sync_page=999")
        page_items, paginator, page_obj = paginate_sync_list(
            request,
            list(range(5)),
            page_param="sync_page",
            per_page_param="sync_per_page",
        )
        self.assertEqual(page_obj.number, 1)
        self.assertEqual(len(page_items), 5)
