"""AG Grid initial filters from nsm_q."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from netbox_nsm.rulebook_rules_grid_payload import build_ag_grid_filter_model
from netbox_nsm.query.parser import Condition, Query, parse


def _rules_layout():
    return [
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
    ]


def _context():
    ctx = MagicMock()
    src = SimpleNamespace(slug="source")
    dst = SimpleNamespace(slug="destination")

    def get_field(name):
        lower = name.lower()
        if lower == "source":
            return src
        if lower == "destination":
            return dst
        return None

    ctx.get_field.side_effect = get_field
    return ctx


class PolicyGridFilterTests(SimpleTestCase):
    def test_name_query_maps_to_name_column(self):
        query = parse('name == "infra-to-dev-2"')
        model = build_ag_grid_filter_model(query, _rules_layout(), _context())
        self.assertEqual(
            model["name"],
            {"filterType": "text", "type": "contains", "filter": "infra-to-dev-2"},
        )

    def test_simple_and_query_maps_to_zone_columns(self):
        query = parse('Source.Name == "dev-1" AND Destination.Name == "dev-2"')
        model = build_ag_grid_filter_model(query, _rules_layout(), _context())
        self.assertEqual(
            model["source::ct_1"],
            {"filterType": "text", "type": "contains", "filter": "dev-1"},
        )
        self.assertEqual(
            model["destination::ct_1"],
            {"filterType": "text", "type": "contains", "filter": "dev-2"},
        )

    def test_typed_zone_query_maps_to_zone_columns(self):
        query = parse(
            'Source.Zones.Name == "PROD:dmz" AND Destination.Zones.Name == "LAN:app"'
        )
        model = build_ag_grid_filter_model(query, _rules_layout(), _context())
        self.assertEqual(
            model["source::ct_1"],
            {"filterType": "text", "type": "contains", "filter": "PROD:dmz"},
        )
        self.assertEqual(
            model["destination::ct_1"],
            {"filterType": "text", "type": "contains", "filter": "LAN:app"},
        )

        query = Query(
            conditions=[],
            or_groups=[
                [
                    Condition(field="Source", sub_field="Name", value="dev-1"),
                    Condition(field="Destination", sub_field="Name", value="dev-2"),
                ],
                [
                    Condition(field="Source", sub_field="Name", value="dev-2"),
                    Condition(field="Destination", sub_field="Name", value="dev-1"),
                ],
            ],
        )
        model = build_ag_grid_filter_model(query, _rules_layout(), _context())
        self.assertEqual(model["source::ct_1"]["operator"], "OR")
        self.assertEqual(
            [c["filter"] for c in model["source::ct_1"]["conditions"]],
            ["dev-1", "dev-2"],
        )
        self.assertEqual(model["destination::ct_1"]["operator"], "OR")
        self.assertEqual(
            [c["filter"] for c in model["destination::ct_1"]["conditions"]],
            ["dev-2", "dev-1"],
        )
