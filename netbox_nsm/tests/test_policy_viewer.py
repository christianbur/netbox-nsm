"""AG Grid payload for Rules tab."""

from django.test import SimpleTestCase

from netbox_nsm.policy_grid_payload import build_policy_ag_grid_payload
from netbox_nsm.views.rulebook import _render_policy_cell_ag


def _sample_grouped():
    return {
        "policy_layout": [
            {"kind": "system", "slug": "status", "label": "Status"},
            {"kind": "system", "slug": "name", "label": "Name"},
            {"kind": "system", "slug": "index", "label": "Index"},
            {"kind": "system", "slug": "description", "label": "Description"},
            {
                "kind": "object",
                "slug": "source",
                "label": "Source",
                "group": {
                    "slug": "source",
                    "label": "Source",
                    "columns": [
                        {
                            "key": "source::ct_1",
                            "label": "Zones",
                            "area_slug": "source",
                        }
                    ],
                },
            },
            {
                "kind": "object",
                "slug": "destination",
                "label": "Destination",
                "group": {
                    "slug": "destination",
                    "label": "Destination",
                    "columns": [
                        {
                            "key": "destination::ct_1",
                            "label": "Zones",
                            "area_slug": "destination",
                        }
                    ],
                },
            },
        ],
        "rows": [
            {
                "pk": 1,
                "edit_url": "/plugins/netbox-nsm/rules/1/edit/",
                "delete_url": "/plugins/netbox-nsm/rules/1/delete/",
                "system": {
                    "enabled": True,
                    "name": "rule-one",
                    "index": 10,
                    "url": "/plugins/netbox-nsm/rules/1/",
                    "description": "Short desc",
                },
                "cells_ag": {
                    "source::ct_1": "<span>cell</span>",
                    "destination::ct_1": "<span>dst</span>",
                },
                "cells_filter": {
                    "source::ct_1": "prod dmz",
                    "destination::ct_1": "lan app",
                },
            }
        ],
    }


class PolicyGridPayloadTests(SimpleTestCase):
    def test_empty_grid_payload(self):
        payload = build_policy_ag_grid_payload({"policy_layout": [], "rows": []})
        self.assertEqual(payload["rowData"], [])
        self.assertEqual(len(payload["columnDefs"]), 1)
        self.assertEqual(payload["columnDefs"][0]["colId"], "_actions")

    def test_ag_cell_uses_dot_and_standard_link(self):
        html = _render_policy_cell_ag(
            [{"url": "/z/1/", "name": "DMZ", "color": "#336699"}],
            max_pills=5,
        )
        self.assertIn("nsm-ag-cell-dot", html)
        self.assertIn("#336699", html)
        self.assertIn("nsm-ag-cell-link", html)
        self.assertNotIn("nsm-rule-pill", html)

    def test_system_columns_use_raw_values(self):
        payload = build_policy_ag_grid_payload(_sample_grouped())
        row = payload["rowData"][0]
        self.assertTrue(row["enabled"])
        self.assertEqual(row["name"], "rule-one")
        self.assertEqual(row["index"], 10)
        self.assertEqual(row["_edit_url"], "/plugins/netbox-nsm/rules/1/edit/")
        self.assertEqual(row["_delete_url"], "/plugins/netbox-nsm/rules/1/delete/")
        self.assertEqual(row["_detail_url"], "/plugins/netbox-nsm/rules/1/")
        self.assertEqual(row["description"], "Short desc")
        self.assertEqual(row["source::ct_1"], "<span>cell</span>")
        self.assertEqual(row["source::ct_1__filter"], "prod dmz")
        self.assertNotIn("_actions_html", row)

    def test_status_column_is_read_only(self):
        payload = build_policy_ag_grid_payload(_sample_grouped())
        status_col = next(
            c for c in payload["columnDefs"] if c.get("colId") == "status"
        )
        self.assertEqual(status_col["field"], "enabled")
        self.assertEqual(status_col["cellRenderer"], "statusCell")
        self.assertNotIn("cellEditor", status_col)
        self.assertNotIn("editableField", status_col)

    def test_index_column_is_read_only(self):
        payload = build_policy_ag_grid_payload(_sample_grouped())
        index_col = next(c for c in payload["columnDefs"] if c.get("colId") == "index")
        self.assertEqual(index_col["field"], "index")
        self.assertEqual(index_col["cellRenderer"], "indexLinkCell")
        self.assertNotIn("cellEditor", index_col)
        self.assertNotIn("editableField", index_col)

    def test_description_column_is_read_only(self):
        payload = build_policy_ag_grid_payload(_sample_grouped())
        desc_col = next(
            c for c in payload["columnDefs"] if c.get("colId") == "description"
        )
        self.assertEqual(desc_col["field"], "description")
        self.assertEqual(desc_col["cellRenderer"], "descriptionCell")
        self.assertNotIn("cellEditor", desc_col)
        self.assertNotIn("editableField", desc_col)

    def test_object_columns_are_read_only(self):
        payload = build_policy_ag_grid_payload(_sample_grouped())
        source_group = next(
            c for c in payload["columnDefs"] if c.get("headerName") == "SOURCE"
        )
        obj_col = source_group["children"][0]
        self.assertEqual(obj_col["cellRenderer"], "htmlCell")
        self.assertNotIn("editViaForm", obj_col)

    def test_actions_column_uses_actions_renderer(self):
        payload = build_policy_ag_grid_payload(_sample_grouped())
        actions_col = next(
            c for c in payload["columnDefs"] if c.get("colId") == "_actions"
        )
        self.assertEqual(actions_col["cellRenderer"], "actionsCell")
        self.assertNotIn("_actions_html", actions_col.get("field", ""))

    def test_object_groups_have_detail_columns(self):
        payload = build_policy_ag_grid_payload(_sample_grouped())
        source_group = next(
            c for c in payload["columnDefs"] if c.get("headerName") == "SOURCE"
        )
        self.assertEqual(len(source_group["children"]), 1)
        self.assertEqual(source_group["children"][0]["field"], "source::ct_1")
        self.assertNotIn("columnGroupShow", source_group["children"][0])
        row = payload["rowData"][0]
        self.assertEqual(row["source::ct_1"], "<span>cell</span>")
        self.assertNotIn("source::__group_summary", row)
