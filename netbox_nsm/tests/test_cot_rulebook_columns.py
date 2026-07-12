"""Display helpers for COT rulebook field columns."""

from types import SimpleNamespace
from unittest.mock import patch

from extras.choices import CustomFieldTypeChoices

from netbox_nsm.rulebooks.rules_layout import (
    build_cot_grouped_rules_table_data,
    build_cot_rules_layout,
    cot_field_allowed_object_labels,
    cot_field_type_display,
)
from utilities.testing import TestCase


class CotFieldTypeDisplayTests(TestCase):
    def test_scalar_field_uses_type_display(self):
        field = SimpleNamespace(
            type=CustomFieldTypeChoices.TYPE_INTEGER,
            get_type_display=lambda: "Integer",
            is_polymorphic=False,
            related_object_type_id=None,
            related_object_types=SimpleNamespace(all=lambda: []),
        )
        self.assertEqual(cot_field_type_display(field), "Integer")
        self.assertEqual(cot_field_allowed_object_labels(field), [])

    def test_multiobject_single_type_includes_allowed_label(self):
        zone_cot = SimpleNamespace(
            slug="nsm_zone",
            verbose_name="Zone",
            name="nsm_zone",
        )
        object_type = SimpleNamespace(
            app_label="netbox_custom_objects",
            model="table99model",
        )
        field = SimpleNamespace(
            type=CustomFieldTypeChoices.TYPE_MULTIOBJECT,
            get_type_display=lambda: "Multiple objects",
            is_polymorphic=False,
            related_object_type_id=1,
            related_object_type=object_type,
            related_object_types=SimpleNamespace(all=lambda: []),
        )
        with patch(
            "netbox_nsm.rulebooks.rules_layout._cot_for_object_type",
            return_value=zone_cot,
        ):
            self.assertEqual(
                cot_field_allowed_object_labels(field),
                ["Zone"],
            )
            self.assertEqual(
                cot_field_type_display(field),
                "Multiple objects (Zone)",
            )

    def test_multiobject_polymorphic_lists_allowed_types(self):
        zone_cot = SimpleNamespace(
            slug="nsm_zone",
            verbose_name="Zone",
            name="nsm_zone",
        )
        label_cot = SimpleNamespace(
            slug="nsm_label",
            verbose_name="Label",
            name="nsm_label",
        )
        zone_type = SimpleNamespace(
            app_label="netbox_custom_objects",
            model="table1model",
        )
        label_type = SimpleNamespace(
            app_label="netbox_custom_objects",
            model="table2model",
        )
        field = SimpleNamespace(
            type=CustomFieldTypeChoices.TYPE_MULTIOBJECT,
            get_type_display=lambda: "Multiple objects",
            is_polymorphic=True,
            related_object_type_id=None,
            related_object_type=None,
            related_object_types=SimpleNamespace(all=lambda: [zone_type, label_type]),
        )
        def _cot_for_mock_object_type(object_type):
            if object_type.model == "table1model":
                return zone_cot
            return label_cot

        with patch(
            "netbox_nsm.rulebooks.rules_layout._cot_for_object_type",
            side_effect=_cot_for_mock_object_type,
        ):
            self.assertEqual(
                cot_field_allowed_object_labels(field),
                ["Zone", "Label"],
            )
            self.assertEqual(
                cot_field_type_display(field),
                "Multiple objects (Zone, Label)",
            )

    def test_layout_adds_extra_columns_from_type_config(self):
        object_type = SimpleNamespace(
            app_label="netbox_custom_objects",
            model="table7model",
        )
        field = SimpleNamespace(
            name="source_zones",
            label="Source Zones",
            group_name="Source",
            type=CustomFieldTypeChoices.TYPE_MULTIOBJECT,
            is_polymorphic=False,
            related_object_type_id=7,
            related_object_type=object_type,
            related_object_types=SimpleNamespace(all=lambda: []),
        )
        fields_qs = SimpleNamespace(
            exclude=lambda **kwargs: SimpleNamespace(order_by=lambda *args: [field])
        )
        cot = SimpleNamespace(fields=fields_qs)

        with (
            patch("netbox_nsm.rulebooks.rules_layout._build_type_config_sort_lookup", return_value={}),
            patch(
                "netbox_nsm.rulebooks.rules_layout._build_type_config_columns_lookup",
                return_value={
                    7: [
                        {
                            "key": "counter",
                            "label": "Counter",
                            "column_order": 100,
                            "value_template": "{{ pk }}",
                        }
                    ]
                },
            ),
            patch(
                "netbox_nsm.rulebooks.rules_layout._content_type_for_object_type",
                return_value=SimpleNamespace(pk=7),
            ),
            patch("netbox_nsm.rulebooks.rules_layout._object_type_label", return_value="Zone"),
        ):
            layout = build_cot_rules_layout(cot)

        keys = [col["key"] for col in layout["grouped_columns"]]
        self.assertIn("source_zones::ct_7", keys)
        self.assertIn("source_zones::ct_7::col_counter", keys)

    def test_grouped_rows_render_extra_column_template_values(self):
        class _Rel:
            def __init__(self, values):
                self._values = values

            def all(self):
                return list(self._values)

        object_field = SimpleNamespace(name="source_zones")
        fields_api = SimpleNamespace(
            filter=lambda **kwargs: [object_field]
        )
        virtual_rb = SimpleNamespace(cot=SimpleNamespace(fields=fields_api), slug="nsm_rb_test")

        obj = SimpleNamespace(name="zone-a", pk=11)
        row_obj = SimpleNamespace(
            pk=101,
            index=1,
            status=True,
            name="Rule A",
            description="",
            source_zones=_Rel([obj]),
        )
        layout = {
            "grouped_columns": [
                {
                    "key": "source_zones::ct_7",
                    "label": "Zone",
                    "area_slug": "source_zones",
                    "type_name": "ct_7",
                },
                {
                    "key": "source_zones::ct_7::col_upper",
                    "label": "Upper",
                    "area_slug": "source_zones",
                    "type_name": "ct_7",
                    "source_key": "source_zones::ct_7",
                    "value_template": "{{ name|upper }}",
                },
            ],
            "rules_layout": [],
        }

        with (
            patch(
                "netbox_nsm.rulebooks.rules_layout.ContentType.objects.get_for_model",
                return_value=SimpleNamespace(pk=7),
            ),
            patch("netbox_nsm.rulebooks.rules_layout.prefetch_interface_parents", return_value=None),
            patch("netbox_nsm.type_metadata.specs.content_type_ids_for_cot_slugs", return_value=[]),
            patch("netbox_nsm.core.display_utils.get_display_template_map", return_value={}),
        ):
            grouped = build_cot_grouped_rules_table_data(
                [row_obj],
                virtual_rb,
                layout=layout,
                include_links=False,
            )

        row = grouped["rows"][0]
        extra = row["cells_items"]["source_zones::ct_7::col_upper"]
        self.assertEqual(extra, [{"name": "ZONE-A"}])

    def test_grouped_rows_split_multiobject_extra_column_values(self):
        class _Rel:
            def __init__(self, values):
                self._values = values

            def all(self):
                return list(self._values)

        object_field = SimpleNamespace(name="source_zones")
        fields_api = SimpleNamespace(
            filter=lambda **kwargs: [object_field]
        )
        virtual_rb = SimpleNamespace(cot=SimpleNamespace(fields=fields_api), slug="nsm_rb_test")

        obj = SimpleNamespace(
            name="segment-a",
            pk=11,
            _field_objects={
                "target": {
                    "name": "target",
                    "field": SimpleNamespace(type=CustomFieldTypeChoices.TYPE_MULTIOBJECT),
                }
            },
        )
        row_obj = SimpleNamespace(
            pk=101,
            index=1,
            status=True,
            name="Rule A",
            description="",
            source_zones=_Rel([obj]),
        )
        layout = {
            "grouped_columns": [
                {
                    "key": "source_zones::ct_7",
                    "label": "Zone",
                    "area_slug": "source_zones",
                    "type_name": "ct_7",
                },
                {
                    "key": "source_zones::ct_7::col_targets",
                    "label": "Targets",
                    "area_slug": "source_zones",
                    "type_name": "ct_7",
                    "source_key": "source_zones::ct_7",
                    "value_template": "{{ target }}",
                },
            ],
            "rules_layout": [],
        }

        with (
            patch(
                "netbox_nsm.rulebooks.rules_layout.ContentType.objects.get_for_model",
                return_value=SimpleNamespace(pk=7),
            ),
            patch("netbox_nsm.rulebooks.rules_layout.prefetch_interface_parents", return_value=None),
            patch("netbox_nsm.type_metadata.specs.content_type_ids_for_cot_slugs", return_value=[]),
            patch("netbox_nsm.core.display_utils.get_display_template_map", return_value={}),
            patch(
                "netbox_nsm.rulebooks.rules_layout.render_display_template",
                return_value="HTTPS (tcp/443), erp-user-url (https://app.erp.example.org)",
            ),
        ):
            grouped = build_cot_grouped_rules_table_data(
                [row_obj],
                virtual_rb,
                layout=layout,
                include_links=False,
            )

        row = grouped["rows"][0]
        extra = row["cells_items"]["source_zones::ct_7::col_targets"]
        self.assertEqual(
            extra,
            [
                {"name": "HTTPS (tcp/443)"},
                {"name": "erp-user-url (https://app.erp.example.org)"},
            ],
        )

    def test_grouped_rows_polymorphic_multiobject_values_are_grouped_by_label(self):
        class _Rel:
            def __init__(self, values):
                self._values = values

            def all(self):
                return list(self._values)

        class _SvcObj:
            def __init__(self, name):
                self.name = name
                self.custom_object_type = SimpleNamespace(verbose_name="Service", name="nsm_service")

        class _UrlObj:
            def __init__(self, name):
                self.name = name
                self.custom_object_type = SimpleNamespace(verbose_name="Address Url", name="nsm_address_url")

        object_field = SimpleNamespace(name="source_zones")
        fields_api = SimpleNamespace(filter=lambda **kwargs: [object_field])
        virtual_rb = SimpleNamespace(cot=SimpleNamespace(fields=fields_api), slug="nsm_rb_test")

        obj = SimpleNamespace(
            name="segment-a",
            pk=11,
            _field_objects={
                "target": {
                    "name": "target",
                    "field": SimpleNamespace(
                        type=CustomFieldTypeChoices.TYPE_MULTIOBJECT,
                        is_polymorphic=True,
                        label="Targets",
                    ),
                }
            },
            target=_Rel([_SvcObj("HTTPS"), _UrlObj("erp-user-url")]),
        )
        row_obj = SimpleNamespace(
            pk=101,
            index=1,
            status=True,
            name="Rule A",
            description="",
            source_zones=_Rel([obj]),
        )
        layout = {
            "grouped_columns": [
                {
                    "key": "source_zones::ct_7",
                    "label": "Zone",
                    "area_slug": "source_zones",
                    "type_name": "ct_7",
                },
                {
                    "key": "source_zones::ct_7::col_targets",
                    "label": "Targets",
                    "area_slug": "source_zones",
                    "type_name": "ct_7",
                    "source_key": "source_zones::ct_7",
                    "value_template": "{{ target }}",
                },
            ],
            "rules_layout": [],
        }

        with (
            patch(
                "netbox_nsm.rulebooks.rules_layout.ContentType.objects.get_for_model",
                side_effect=[SimpleNamespace(pk=7), SimpleNamespace(pk=10), SimpleNamespace(pk=11)],
            ),
            patch("netbox_nsm.rulebooks.rules_layout.prefetch_interface_parents", return_value=None),
            patch("netbox_nsm.type_metadata.specs.content_type_ids_for_cot_slugs", return_value=[]),
            patch("netbox_nsm.core.display_utils.get_display_template_map", return_value={}),
            patch(
                "netbox_nsm.core.display_utils.render_object_display",
                side_effect=["HTTPS (tcp/443)", "erp-user-url ()"],
            ),
        ):
            grouped = build_cot_grouped_rules_table_data(
                [row_obj],
                virtual_rb,
                layout=layout,
                include_links=False,
            )

        row = grouped["rows"][0]
        extra = row["cells_items"]["source_zones::ct_7::col_targets"]
        self.assertEqual(
            extra,
            [
                {"name": "Service (Target)", "group_label": True},
                {"name": "HTTPS (tcp/443)", "group_item": True},
                {"name": "Address Url (Target)", "group_label": True},
                {"name": "erp-user-url ()", "group_item": True},
            ],
        )

    def test_grouped_rows_polymorphic_group_items_include_object_urls(self):
        class _Rel:
            def __init__(self, values):
                self._values = values

            def all(self):
                return list(self._values)

        class _SvcObj:
            def __init__(self, name):
                self.name = name
                self.custom_object_type = SimpleNamespace(
                    verbose_name="Service",
                    name="nsm_service",
                    slug="nsm_service",
                )
                self.pk = 101

        class _UrlObj:
            def __init__(self, name):
                self.name = name
                self.custom_object_type = SimpleNamespace(
                    verbose_name="Address Url",
                    name="nsm_address_url",
                    slug="nsm_address_url",
                )
                self.pk = 202

        object_field = SimpleNamespace(name="source_zones")
        fields_api = SimpleNamespace(filter=lambda **kwargs: [object_field])
        virtual_rb = SimpleNamespace(cot=SimpleNamespace(fields=fields_api), slug="nsm_rb_test")

        obj = SimpleNamespace(
            name="segment-a",
            pk=11,
            _field_objects={
                "target": {
                    "name": "target",
                    "field": SimpleNamespace(
                        type=CustomFieldTypeChoices.TYPE_MULTIOBJECT,
                        is_polymorphic=True,
                        label="Target",
                    ),
                }
            },
            source_zones=[],
            target=_Rel([_SvcObj("HTTPS"), _UrlObj("erp-user-url")]),
        )
        row_obj = SimpleNamespace(
            pk=101,
            index=1,
            status=True,
            name="Rule A",
            description="",
            source_zones=_Rel([obj]),
        )
        layout = {
            "grouped_columns": [
                {
                    "key": "source_zones::ct_7",
                    "label": "Zone",
                    "area_slug": "source_zones",
                    "type_name": "ct_7",
                },
                {
                    "key": "source_zones::ct_7::col_targets",
                    "label": "Targets",
                    "area_slug": "source_zones",
                    "type_name": "ct_7",
                    "source_key": "source_zones::ct_7",
                    "value_template": "{{ target }}",
                },
            ],
            "rules_layout": [],
        }

        with (
            patch(
                "netbox_nsm.rulebooks.rules_layout.ContentType.objects.get_for_model",
                side_effect=[SimpleNamespace(pk=7), SimpleNamespace(pk=10), SimpleNamespace(pk=11)],
            ),
            patch("netbox_nsm.rulebooks.rules_layout.prefetch_interface_parents", return_value=None),
            patch("netbox_nsm.type_metadata.specs.content_type_ids_for_cot_slugs", return_value=[]),
            patch("netbox_nsm.core.display_utils.get_display_template_map", return_value={}),
            patch(
                "netbox_nsm.core.display_utils.render_object_display",
                side_effect=["HTTPS (tcp/443)", "erp-user-url ()"],
            ),
            patch(
                "netbox_nsm.objects.cot_routes.nsm_object_reverse",
                side_effect=[
                    "/plugins/netbox-nsm/objects/nsm_service/101/",
                    "/plugins/netbox-nsm/objects/nsm_address_url/202/",
                ],
            ),
        ):
            grouped = build_cot_grouped_rules_table_data(
                [row_obj],
                virtual_rb,
                layout=layout,
                include_links=True,
            )

        row = grouped["rows"][0]
        extra = row["cells_items"]["source_zones::ct_7::col_targets"]
        self.assertEqual(extra[1].get("url"), "/plugins/netbox-nsm/objects/nsm_service/101/")
        self.assertEqual(extra[3].get("url"), "/plugins/netbox-nsm/objects/nsm_address_url/202/")

    def test_grouped_rows_object_field_extra_column_includes_object_url(self):
        class _Rel:
            def __init__(self, values):
                self._values = values

            def all(self):
                return list(self._values)

        related_app = SimpleNamespace(
            pk=301,
            custom_object_type=SimpleNamespace(slug="nsm_app_business"),
        )

        obj = SimpleNamespace(
            name="segment-a",
            pk=11,
            _field_objects={
                "app_business": {
                    "name": "app_business",
                    "field": SimpleNamespace(type=CustomFieldTypeChoices.TYPE_OBJECT),
                }
            },
            app_business=related_app,
        )

        object_field = SimpleNamespace(name="source_zones")
        fields_api = SimpleNamespace(filter=lambda **kwargs: [object_field])
        virtual_rb = SimpleNamespace(cot=SimpleNamespace(fields=fields_api), slug="nsm_rb_test")
        row_obj = SimpleNamespace(
            pk=101,
            index=1,
            status=True,
            name="Rule A",
            description="",
            source_zones=_Rel([obj]),
        )
        layout = {
            "grouped_columns": [
                {
                    "key": "source_zones::ct_7",
                    "label": "Zone",
                    "area_slug": "source_zones",
                    "type_name": "ct_7",
                },
                {
                    "key": "source_zones::ct_7::col_app",
                    "label": "Business App",
                    "area_slug": "source_zones",
                    "type_name": "ct_7",
                    "source_key": "source_zones::ct_7",
                    "value_template": "{{ app_business }}",
                },
            ],
            "rules_layout": [],
        }

        with (
            patch(
                "netbox_nsm.rulebooks.rules_layout.ContentType.objects.get_for_model",
                return_value=SimpleNamespace(pk=7),
            ),
            patch("netbox_nsm.rulebooks.rules_layout.prefetch_interface_parents", return_value=None),
            patch("netbox_nsm.type_metadata.specs.content_type_ids_for_cot_slugs", return_value=[]),
            patch("netbox_nsm.core.display_utils.get_display_template_map", return_value={}),
            patch("netbox_nsm.rulebooks.rules_layout.render_display_template", return_value="ERP-Core"),
            patch("netbox_nsm.rulebooks.rules_layout.cot_has_menu", return_value=True),
            patch(
                "netbox_nsm.objects.cot_routes.nsm_object_reverse",
                return_value="/plugins/netbox-nsm/objects/nsm_app_business/301/",
            ),
        ):
            grouped = build_cot_grouped_rules_table_data(
                [row_obj],
                virtual_rb,
                layout=layout,
                include_links=True,
            )

        row = grouped["rows"][0]
        extra = row["cells_items"]["source_zones::ct_7::col_app"]
        self.assertEqual(extra, [{"name": "ERP-Core", "url": "/plugins/netbox-nsm/objects/nsm_app_business/301/"}])

    def test_grouped_rows_extra_columns_are_separated_per_segment(self):
        class _Rel:
            def __init__(self, values):
                self._values = values

            def all(self):
                return list(self._values)

        segment_a = SimpleNamespace(
            name="erp-src-admin",
            pk=11,
            custom_object_type=SimpleNamespace(slug="nsm_app_business_segment"),
            _field_objects={
                "app_business": {
                    "name": "app_business",
                    "field": SimpleNamespace(type=CustomFieldTypeChoices.TYPE_OBJECT),
                }
            },
            app_business=SimpleNamespace(pk=301, custom_object_type=SimpleNamespace(slug="nsm_app_business")),
        )
        segment_b = SimpleNamespace(
            name="erp-src-users",
            pk=12,
            custom_object_type=SimpleNamespace(slug="nsm_app_business_segment"),
            _field_objects={
                "app_business": {
                    "name": "app_business",
                    "field": SimpleNamespace(type=CustomFieldTypeChoices.TYPE_OBJECT),
                }
            },
            app_business=SimpleNamespace(pk=302, custom_object_type=SimpleNamespace(slug="nsm_app_business")),
        )

        object_field = SimpleNamespace(name="source_segments")
        fields_api = SimpleNamespace(filter=lambda **kwargs: [object_field])
        virtual_rb = SimpleNamespace(cot=SimpleNamespace(fields=fields_api), slug="nsm_rb_test")
        row_obj = SimpleNamespace(
            pk=101,
            index=1,
            status=True,
            name="Rule A",
            description="",
            source_segments=_Rel([segment_a, segment_b]),
        )
        layout = {
            "grouped_columns": [
                {
                    "key": "source_segments::ct_7",
                    "label": "Segment",
                    "area_slug": "source_segments",
                    "type_name": "ct_7",
                },
                {
                    "key": "source_segments::ct_7::col_app",
                    "label": "Business App",
                    "area_slug": "source_segments",
                    "type_name": "ct_7",
                    "source_key": "source_segments::ct_7",
                    "value_template": "{{ app_business }}",
                },
            ],
            "rules_layout": [],
        }

        with (
            patch(
                "netbox_nsm.rulebooks.rules_layout.ContentType.objects.get_for_model",
                side_effect=[SimpleNamespace(pk=7), SimpleNamespace(pk=7)],
            ),
            patch("netbox_nsm.rulebooks.rules_layout.prefetch_interface_parents", return_value=None),
            patch("netbox_nsm.type_metadata.specs.content_type_ids_for_cot_slugs", return_value=[]),
            patch("netbox_nsm.core.display_utils.get_display_template_map", return_value={}),
            patch(
                "netbox_nsm.rulebooks.rules_layout._object_item_dict",
                side_effect=[
                    {"name": "erp-src-admin", "url": "/plugins/netbox-nsm/objects/nsm_app_business_segment/11/"},
                    {"name": "erp-src-users", "url": "/plugins/netbox-nsm/objects/nsm_app_business_segment/12/"},
                ],
            ),
            patch(
                "netbox_nsm.rulebooks.rules_layout.render_display_template",
                side_effect=["ERP-Core", "ERP-Core"],
            ),
            patch("netbox_nsm.rulebooks.rules_layout.cot_has_menu", return_value=False),
        ):
            grouped = build_cot_grouped_rules_table_data(
                [row_obj],
                virtual_rb,
                layout=layout,
                include_links=True,
            )

        row = grouped["rows"][0]
        extra = row["cells_items"]["source_segments::ct_7::col_app"]
        self.assertEqual(
            extra[0],
            {
                "name": "erp-src-admin",
                "segment_label": True,
                "segment_type_label": "Segment",
                "url": "/plugins/netbox-nsm/objects/nsm_app_business_segment/11/",
            },
        )
        self.assertEqual(extra[1]["name"], "ERP-Core")
        self.assertTrue(extra[2].get("segment_break"))
        self.assertEqual(
            extra[3],
            {
                "name": "erp-src-users",
                "segment_label": True,
                "segment_type_label": "Segment",
                "url": "/plugins/netbox-nsm/objects/nsm_app_business_segment/12/",
            },
        )
        self.assertEqual(extra[4]["name"], "ERP-Core")
