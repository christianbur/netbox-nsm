"""Tests for nsm_addresses → IPAM FK panel references."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.objects.address_ipam_fk import (
    NSM_ADDRESSES_SLUG,
    is_nsm_address_object,
    iter_address_ipam_fk_refs,
    iter_addresses_for_ipam_object,
    panel_link_type_for_address_ipam_fk,
)


class AddressIpamFkRefTests(SimpleTestCase):
    @patch("django.contrib.contenttypes.models.ContentType.objects.get_for_model")
    def test_iter_yields_prefix_ip_and_range(self, get_for_model):
        prefix = SimpleNamespace(pk=10, prefix="10.245.10.0/24")
        ip = SimpleNamespace(pk=20, address="10.246.10.1/32")
        ip_range = SimpleNamespace(pk=30, start_address="10.247.10.10/32")

        def _ct(obj):
            return SimpleNamespace(
                pk=100 + id(obj),
                app_label="ipam",
                model=type(obj).__name__.lower(),
            )

        get_for_model.side_effect = _ct

        addr = SimpleNamespace(
            prefix_id=10,
            prefix=prefix,
            ip_address_id=20,
            ip_address=ip,
            range_id=30,
            range=ip_range,
        )
        refs = list(iter_address_ipam_fk_refs(addr))
        self.assertEqual(len(refs), 3)
        self.assertEqual(refs[0].field_name, "prefix")
        self.assertIs(refs[0].ipam_obj, prefix)
        self.assertEqual(refs[1].field_name, "ip_address")
        self.assertEqual(refs[2].field_name, "range")

    @patch("django.contrib.contenttypes.models.ContentType.objects.get")
    @patch("django.contrib.contenttypes.models.ContentType.objects.get_for_model")
    def test_iter_polymorphic_address_field(self, get_for_model, get_ct):
        prefix = SimpleNamespace(pk=10, prefix="10.245.10.0/24")
        ct = SimpleNamespace(pk=55, app_label="ipam", model="prefix")
        get_ct.return_value = ct

        model = MagicMock()
        model.objects.filter.return_value.first.return_value = prefix
        ct.model_class = MagicMock(return_value=model)

        addr = SimpleNamespace(
            address_content_type_id=55,
            address_object_id=10,
            prefix_id=None,
            prefix=None,
            ip_address_id=None,
            ip_address=None,
            range_id=None,
            range=None,
        )
        refs = list(iter_address_ipam_fk_refs(addr))
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].field_name, "address")
        self.assertIs(refs[0].ipam_obj, prefix)

    @patch("django.contrib.contenttypes.models.ContentType.objects.get_for_model")
    def test_iter_skips_empty_fk(self, get_for_model):
        addr = SimpleNamespace(
            prefix_id=None,
            prefix=None,
            ip_address_id=None,
            ip_address=None,
            range_id=None,
            range=None,
        )
        self.assertEqual(list(iter_address_ipam_fk_refs(addr)), [])

    @patch("netbox_nsm.addresses.address_ipam_fk.get_nsm_address_model")
    @patch("django.contrib.contenttypes.models.ContentType.objects.get_for_model")
    def test_iter_addresses_for_ipam_object_polymorphic(
        self, get_for_model, get_addr_model
    ):
        prefix = SimpleNamespace(pk=10, prefix="10.112.146.0/24")
        addr_a = SimpleNamespace(pk=1, name="dm-addr-10-112-146-0-24")
        addr_b = SimpleNamespace(pk=2, name="dm-addr-legacy")

        addr_model = MagicMock()
        addr_model.objects.filter.return_value.order_by.return_value = [addr_a]
        get_addr_model.return_value = addr_model

        ipam_ct = SimpleNamespace(pk=70)
        get_for_model.return_value = ipam_ct

        rows = list(iter_addresses_for_ipam_object(prefix))
        self.assertEqual(len(rows), 1)
        self.assertIs(rows[0][0], addr_a)
        self.assertEqual(rows[0][1], "address")
        addr_model.objects.filter.assert_called_with(
            address_content_type_id=70,
            address_object_id=10,
        )

    @patch("netbox_nsm.addresses.address_ipam_fk.get_nsm_address_model")
    @patch("django.contrib.contenttypes.models.ContentType.objects.get_for_model")
    def test_addresses_for_ipam_object_queryset_polymorphic(
        self, get_for_model, get_addr_model
    ):
        from django.db.models import Q

        from netbox_nsm.objects.address_ipam_fk import (
            addresses_for_ipam_object_queryset,
        )

        prefix = SimpleNamespace(pk=10)
        addr_model = MagicMock()
        none_qs = MagicMock()
        addr_model.objects.none.return_value = none_qs
        filtered_qs = MagicMock()
        addr_model.objects.filter.return_value = filtered_qs
        get_addr_model.return_value = addr_model
        get_for_model.return_value = SimpleNamespace(pk=70)

        result = addresses_for_ipam_object_queryset(addr_model, prefix)
        self.assertIs(result, filtered_qs)
        addr_model.objects.filter.assert_called_once()
        q = addr_model.objects.filter.call_args[0][0]
        self.assertIsInstance(q, Q)

    def test_fk_field_name_from_filter_prefix(self):
        from netbox_nsm.objects.address_ipam_fk import fk_field_name_from_filter

        self.assertEqual(fk_field_name_from_filter({"prefix_id": 5}), "prefix")
        self.assertEqual(fk_field_name_from_filter({"ip_address_id": 1}), "ip_address")
        self.assertEqual(
            fk_field_name_from_filter(
                {"address_content_type_id": 1, "address_object_id": 2}
            ),
            "address",
        )
        self.assertIsNone(fk_field_name_from_filter({}))

    def test_panel_link_type_labels_prefix(self):
        label = panel_link_type_for_address_ipam_fk("prefix")
        self.assertIn("Prefix", label)
        self.assertIn("IPAM", label)

    @patch("netbox_nsm.addresses.address_ipam_fk.cot_ipam_address_flag", return_value=True)
    @patch("netbox_nsm.addresses.address_ipam_fk.get_nsm_address_model")
    def test_is_nsm_address_object_uses_custom_object_type_slug(self, get_model, _flag):
        stale_model = type("StaleTable3Model", (), {})
        fresh_model = type("FreshTable3Model", (), {})
        get_model.return_value = fresh_model

        addr = SimpleNamespace(
            custom_object_type=SimpleNamespace(slug=NSM_ADDRESSES_SLUG),
        )
        self.assertTrue(is_nsm_address_object(addr))

        with patch(
            "netbox_nsm.addresses.address_ipam_fk.cot_ipam_address_flag",
            return_value=False,
        ):
            other = SimpleNamespace(
                custom_object_type=SimpleNamespace(slug="nsm_zones"),
            )
            self.assertFalse(is_nsm_address_object(other))

        class StaleAddr(stale_model):
            pass

        legacy = StaleAddr()
        self.assertTrue(is_nsm_address_object(legacy, addr_model=stale_model))
        self.assertFalse(is_nsm_address_object(legacy, addr_model=fresh_model))
