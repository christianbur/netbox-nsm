"""Security tab: nsm_object_link junction rows (link-table metadata, no duplicates)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.security.tab.combined import (
    _JunctionField,
    _cot_is_junction,
    _far_field,
    _transform_junctions,
    is_untransformed_junction_row,
)
from netbox_nsm.security.tab.links import prepare_link_tab_view
from netbox_nsm.security.tab.security_rows import append_cot_reference_link_groups


def _link_cot(*, slug="nsm_object_link", link_table=False, name="Object Links"):
    return SimpleNamespace(
        slug=slug,
        link_table=link_table,
        pk=99,
        comments="",
        metadata="",
        __str__=lambda self: name,
    )


def _zone(pk=5, name="demo-addr-zone-01"):
    zone_cot = SimpleNamespace(slug="nsm_zone", __str__=lambda self: "Zones")
    return SimpleNamespace(
        pk=pk,
        custom_object_type=zone_cot,
        get_absolute_url=lambda: f"/plugins/custom-objects/nsm_zone/{pk}/",
        __str__=lambda self: name,
    )


def _interface(pk=1, name="GigabitEthernet0/0/0"):
    return SimpleNamespace(
        pk=pk,
        get_absolute_url=lambda: f"/dcim/interfaces/{pk}/",
        __str__=lambda self: name,
    )


def _object_link_row(*, iface, zone, link_table=True):
    cot = _link_cot(link_table=link_table)
    netbox_field = SimpleNamespace(
        name="netbox_object",
        custom_object_type=cot,
        type="object",
        is_polymorphic=True,
    )
    row = SimpleNamespace(
        pk=42,
        custom_object_type=cot,
        netbox_object=iface,
        policy_object=zone,
        get_absolute_url=lambda: "/plugins/custom-objects/nsm_object_link/42/",
        __str__=lambda self: f"{iface} → {zone}",
    )
    return row, netbox_field


class CotIsJunctionTests(SimpleTestCase):
    def test_link_table_flag_marks_junction(self):
        self.assertTrue(_cot_is_junction(_link_cot(link_table=True)))

    def test_without_link_table_not_junction(self):
        self.assertFalse(_cot_is_junction(_link_cot(link_table=False)))

    @patch("netbox_nsm.security.tab.combined.cot_link_table_flag", return_value=True)
    def test_link_table_flag_also_counts(self, _mock_flag):
        self.assertTrue(_cot_is_junction(SimpleNamespace(slug="other", link_table=True)))

    def test_ordinary_cot_is_not_junction(self):
        self.assertFalse(_cot_is_junction(SimpleNamespace(slug="nsm_zone", link_table=False)))


class FarFieldTests(SimpleTestCase):
    @patch("netbox_nsm.security.tab.combined._object_fields_for_cot")
    def test_resolves_other_object_field_without_slug_mapping(self, mock_fields):
        cot = _link_cot(link_table=True)
        near = SimpleNamespace(name="netbox_object", custom_object_type=cot)
        policy_field = SimpleNamespace(name="policy_object")
        netbox_field = SimpleNamespace(name="netbox_object")
        mock_fields.return_value = [policy_field, netbox_field]

        far = _far_field(near)

        self.assertEqual(far.name, "policy_object")


class TransformJunctionsTests(SimpleTestCase):
    @patch("netbox_nsm.security.tab.combined._object_fields_for_cot")
    def test_rewrites_nsm_object_link_to_zone_with_via_metadata(self, mock_fields):
        iface = _interface()
        zone = _zone()
        row, field = _object_link_row(iface=iface, zone=zone)
        mock_fields.return_value = [
            SimpleNamespace(name="policy_object"),
            SimpleNamespace(name="netbox_object"),
        ]

        transformed = _transform_junctions([(row, field)])

        self.assertEqual(len(transformed), 1)
        endpoint, jfield = transformed[0]
        self.assertIs(endpoint, zone)
        self.assertTrue(jfield.is_junction_row)
        self.assertIs(jfield.via_obj, row)

    def test_leaves_non_junction_rows_untouched(self):
        cot = SimpleNamespace(slug="nsm_zone", link_table=False)
        field = SimpleNamespace(name="parent", custom_object_type=cot, type="object")
        obj = SimpleNamespace(pk=1, custom_object_type=cot)

        transformed = _transform_junctions([(obj, field)])

        self.assertEqual(transformed, [(obj, field)])


class UntransformedJunctionRowTests(SimpleTestCase):
    def test_detects_raw_object_link_row(self):
        row, field = _object_link_row(
            iface=_interface(),
            zone=_zone(),
        )
        self.assertTrue(is_untransformed_junction_row(row, field))

    @patch("netbox_nsm.security.tab.combined._object_fields_for_cot")
    def test_junction_rewrite_is_not_untransformed(self, mock_fields):
        row, field = _object_link_row(iface=_interface(), zone=_zone())
        mock_fields.return_value = [
            SimpleNamespace(name="policy_object"),
            SimpleNamespace(name="netbox_object"),
        ]
        endpoint, jfield = _transform_junctions([(row, field)])[0]
        self.assertFalse(is_untransformed_junction_row(endpoint, jfield))


class AppendCotReferenceSkipsRawObjectLinkTests(SimpleTestCase):
    @patch("netbox_nsm.security.tab.security_rows._get_linked_custom_objects")
    def test_skips_untransformed_nsm_object_link_rows(self, mock_get_linked):
        row, field = _object_link_row(iface=_interface(), zone=_zone())
        mock_get_linked.return_value = [(row, field)]

        links_by_type: dict = {}
        added = append_cot_reference_link_groups(
            links_by_type,
            _interface(),
            RequestFactory().get("/dcim/interfaces/1/security/"),
            panel_link_payload=lambda *a, **k: {"obj_id": k.get("obj_id", 0), **k},
            tmpl_map={},
            type_label_fn=lambda _ct: "Zones",
            return_url="/dcim/interfaces/1/security/",
        )

        self.assertEqual(added, 0)
        self.assertEqual(links_by_type, {})


class InterfaceSecurityTableIntegrationTests(SimpleTestCase):
    """Flat table shows zone + via link-table metadata, not Object Links type."""

    def test_junction_row_renders_via_in_value_column(self):
        zone = _zone()
        link_row = SimpleNamespace(
            pk=42,
            get_absolute_url=lambda: "/plugins/custom-objects/nsm_object_link/42/",
            __str__=lambda self: "GigabitEthernet0/0/0 → demo-addr-zone-01",
        )
        jfield = _JunctionField(
            _link_cot(),
            "Zones",
            link_row,
            "linked via Object Links",
        )

        groups = [
            {
                "type_key": "netbox_custom_objects__table5model",
                "type_label": "Zones",
                "count": 1,
                "objects": [
                    {
                        "url": zone.get_absolute_url(),
                        "name": "demo-addr-zone-01",
                        "row_type_label": "Zones",
                        "row_type_filter_key": "netbox_custom_objects__table5model",
                        "obj_id": zone.pk,
                        "is_junction_row": True,
                        "via_obj_url": link_row.get_absolute_url(),
                        "via_obj_name": "GigabitEthernet0/0/0 → demo-addr-zone-01",
                        "field_label": str(jfield),
                        "value_key": "_none",
                        "value_label": "",
                    }
                ],
            }
        ]

        ctx = prepare_link_tab_view(groups, RequestFactory().get("/dcim/interfaces/1/security/"))
        html = render_to_string(
            "netbox_nsm/inc/security_link_objects.html",
            ctx,
        )

        self.assertEqual(ctx["nsm_link_count"], 1)
        self.assertIn("demo-addr-zone-01", html)
        self.assertIn("via", html)
        self.assertIn("GigabitEthernet0/0/0 → demo-addr-zone-01", html)
        self.assertIn('class="col-type">Zones', html)
        self.assertNotIn('class="col-type">Object Links', html)

    @patch(
        "netbox_nsm.security.tab.context.build_cot_security_rulebook_groups",
        return_value={"rulebook_groups": [], "unique_rules_total": 0},
    )
    @patch(
        "netbox_nsm.security.links.object_link_service.build_panel_link_groups",
    )
    @patch("netbox_nsm.security.tab.context.append_cot_reference_link_groups")
    @patch("netbox_nsm.security.tab.context.get_display_template_map", return_value={})
    @patch("netbox_nsm.security.tab.context.ContentType")
    def test_security_tab_uses_only_cot_reference_path(
        self,
        mock_ct,
        _mock_tmpl,
        mock_append,
        mock_panel,
        _mock_rulebooks,
    ):
        from netbox_nsm.security.tab.context import build_security_tab_context

        def _append(links_by_type, obj, request, **kwargs):
            links_by_type["netbox_custom_objects__zone"] = {
                "label": "Zones",
                "objects": [
                    {
                        "url": "/zones/5/",
                        "name": "demo-addr-zone-01",
                        "obj_id": 5,
                        "is_junction_row": True,
                        "row_type_filter_key": "netbox_custom_objects__zone",
                        "row_type_label": "Zones",
                        "field_label": "linked via Object Links",
                        "via_obj_url": "/links/42/",
                        "via_obj_name": "GigabitEthernet0/0/0 → demo-addr-zone-01",
                    }
                ],
            }
            return 1

        mock_append.side_effect = _append
        mock_ct.objects.get_for_model.return_value = MagicMock(pk=1)

        obj = MagicMock(pk=1)
        ctx = build_security_tab_context(
            obj,
            RequestFactory().get("/dcim/interfaces/1/security/"),
        )

        mock_panel.assert_not_called()
        table = ctx["nsm_link_table"]
        self.assertIsNotNone(table)
        self.assertEqual(len(table["page"]), 1)
        row = table["page"][0]
        self.assertTrue(row.get("is_junction_row"))
        self.assertEqual(row["field_label"], "linked via Object Links")

    @patch(
        "netbox_nsm.security.tab.context.build_cot_security_rulebook_groups",
        return_value={"rulebook_groups": [], "unique_rules_total": 0},
    )
    @patch(
        "netbox_nsm.security.links.object_link_service.build_panel_link_groups",
    )
    @patch("netbox_nsm.security.tab.context.append_cot_reference_link_groups")
    @patch("netbox_nsm.security.tab.context.get_display_template_map", return_value={})
    @patch("netbox_nsm.security.tab.context.ContentType")
    def test_zone_tab_shows_junction_interface_row_from_single_path(
        self,
        mock_ct,
        _mock_tmpl,
        mock_append,
        mock_panel,
        _mock_rulebooks,
    ):
        """Zone/address Security tab: one junction row per linked interface."""
        from netbox_nsm.security.tab.context import build_security_tab_context

        def _append(links_by_type, obj, request, **kwargs):
            links_by_type["dcim__interface"] = {
                "label": "Interfaces",
                "objects": [
                    {
                        "url": "/dcim/interfaces/1/",
                        "name": "dmi01-akron-rtr01 / GigabitEthernet0/0/0",
                        "obj_id": 1,
                        "is_junction_row": True,
                        "row_type_filter_key": "nsm_object_link",
                        "row_type_label": "Interfaces",
                        "field_label": "linked via Object Links",
                        "via_obj_url": "/links/42/",
                        "via_obj_name": "GigabitEthernet0/0/0 → demo-addr-zone-01",
                    }
                ],
            }
            return 1

        mock_append.side_effect = _append
        mock_ct.objects.get_for_model.return_value = MagicMock(pk=1)

        obj = MagicMock(pk=5)
        ctx = build_security_tab_context(
            obj,
            RequestFactory().get("/plugins/custom-objects/nsm_zone/5/security/"),
        )

        mock_panel.assert_not_called()
        table = ctx["nsm_link_table"]
        self.assertIsNotNone(table)
        self.assertEqual(len(table["page"]), 1)
        row = table["page"][0]
        self.assertTrue(row.get("is_junction_row"))
        self.assertIn("GigabitEthernet0/0/0", row.get("via_obj_name", ""))
        self.assertEqual(row["field_label"], "linked via Object Links")
