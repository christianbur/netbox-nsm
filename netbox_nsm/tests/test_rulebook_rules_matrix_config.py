"""Matrix dropzone validation for embedded Rules tab matrix mode."""

from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.rulebook_rules_matrix import (
    MATRIX_NOT_ALLOWED_MESSAGE,
    MATRIX_TYPE_MISMATCH_MESSAGE,
    build_matrix_column_meta,
    build_rules_matrix_grid_config,
    parse_matrix_column_levels,
    validate_matrix_column_pair,
)


def _sample_layout():
    return [
        {
            "kind": "object",
            "slug": "source",
            "label": "Source",
            "group": {
                "columns": [
                    {
                        "key": "source::ct_10",
                        "label": "Zones",
                        "type_name": "ct_10",
                    }
                ],
            },
        },
        {
            "kind": "object",
            "slug": "destination",
            "label": "Destination",
            "group": {
                "columns": [
                    {
                        "key": "destination::ct_10",
                        "label": "Zones",
                        "type_name": "ct_10",
                    }
                ],
            },
        },
        {
            "kind": "object",
            "slug": "source",
            "label": "Source",
            "group": {
                "columns": [
                    {
                        "key": "source::Groups",
                        "label": "Groups",
                        "type_name": "Groups",
                    }
                ],
            },
        },
    ]


class RulebookRulesMatrixMetaTests(SimpleTestCase):
    def test_build_matrix_column_meta_skips_groups(self):
        meta = build_matrix_column_meta(
            _sample_layout(),
            {"source": "source", "destination": "destination"},
        )
        self.assertIn("col:source::ct_10", meta)
        self.assertIn("col:destination::ct_10", meta)
        self.assertNotIn("col:source::Groups", meta)
        self.assertEqual(meta["col:source::ct_10"]["placement"], "source")
        self.assertEqual(meta["col:destination::ct_10"]["contentTypeId"], 10)

    def test_validate_matching_source_destination_zones(self):
        meta = build_matrix_column_meta(
            _sample_layout(),
            {"source": "source", "destination": "destination"},
        )
        self.assertIsNone(
            validate_matrix_column_pair(
                "col:source::ct_10",
                "col:destination::ct_10",
                meta,
            )
        )

    def test_validate_same_column_twice(self):
        meta = build_matrix_column_meta(
            _sample_layout(),
            {"source": "source", "destination": "destination"},
        )
        self.assertIsNone(
            validate_matrix_column_pair(
                "col:source::ct_10",
                "col:source::ct_10",
                meta,
            )
        )

    def test_validate_rejects_incompatible_type(self):
        layout = _sample_layout() + [
            {
                "kind": "object",
                "slug": "destination",
                "label": "Destination",
                "group": {
                    "columns": [
                        {
                            "key": "destination::ct_99",
                            "label": "Networks",
                            "type_name": "ct_99",
                        }
                    ],
                },
            }
        ]
        meta = build_matrix_column_meta(
            layout,
            {"source": "source", "destination": "destination"},
        )
        err = validate_matrix_column_pair(
            "col:source::ct_10",
            "col:destination::ct_99",
            meta,
        )
        self.assertEqual(err, str(MATRIX_TYPE_MISMATCH_MESSAGE))

    def test_validate_rejects_tags_and_unknown(self):
        meta = build_matrix_column_meta(_sample_layout(), {})
        self.assertEqual(
            validate_matrix_column_pair("tag:source", "col:source::ct_10", meta),
            str(MATRIX_NOT_ALLOWED_MESSAGE),
        )


class RulebookRulesMatrixConfigTests(SimpleTestCase):
    def test_matrix_config_from_url(self):
        request = RequestFactory().get(
            "/rules/?matrix_row=col:source::ct_10&matrix_col=col:destination::ct_10"
        )
        instance = type("RB", (), {"pk": 2, "name": "Demo Policy"})()
        cfg = build_rules_matrix_grid_config(
            request,
            instance,
            _sample_layout(),
            field_placements={"source": "source", "destination": "destination"},
        )
        self.assertTrue(cfg["matrixEnabled"])
        self.assertEqual(cfg["matrixRow"], "col:source::ct_10")
        self.assertEqual(cfg["matrixCol"], "col:destination::ct_10")
        self.assertEqual(cfg["matrixContentTypeId"], 10)
        self.assertIn("matrixGridUrl", cfg)
        self.assertEqual(cfg["matrixMode"], "directed")

    def test_matrix_config_respects_mode_param(self):
        request = RequestFactory().get(
            "/rules/?matrix_row=col:source::ct_10&matrix_col=col:destination::ct_10&mode=undirected"
        )
        instance = type("RB", (), {"pk": 2, "name": "Demo Policy"})()
        cfg = build_rules_matrix_grid_config(
            request,
            instance,
            _sample_layout(),
            field_placements={"source": "source", "destination": "destination"},
        )
        self.assertEqual(cfg["matrixMode"], "undirected")
        self.assertNotIn("showMatrixModeToggle", cfg)
        request = RequestFactory().get(
            "/rules/?matrix_row=col:source::ct_10&matrix_col=col:destination::ct_99"
        )
        meta = build_matrix_column_meta(
            _sample_layout(),
            {"source": "source", "destination": "destination"},
        )
        self.assertIsNone(parse_matrix_column_levels(request, matrix_column_meta=meta))
