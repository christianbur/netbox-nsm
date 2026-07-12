from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from netbox_nsm.core.display_template import build_display_template_context


class _RelManager:
    def __init__(self, items):
        self._items = list(items)

    def all(self):
        return list(self._items)


class _RefObject:
    def __init__(self, name: str):
        self.name = name

    def __str__(self):
        return self.name


class DisplayTemplateContextTests(SimpleTestCase):
    def test_multiobject_field_uses_type_display_templates(self):
        obj = SimpleNamespace(
            _field_objects={
                "target": {
                    "name": "target",
                    "field": SimpleNamespace(type="multiobject"),
                }
            },
            target=_RelManager([_RefObject("HTTPS"), _RefObject("erp-user-url")]),
        )

        with patch(
            "django.contrib.contenttypes.models.ContentType.objects.get_for_model",
            side_effect=[SimpleNamespace(pk=1), SimpleNamespace(pk=2)],
        ), patch(
            "netbox_nsm.core.display_utils.get_display_template_map",
            return_value={1: "{{ name }}", 2: "{{ name }}"},
        ), patch(
            "netbox_nsm.core.display_utils.render_object_display",
            side_effect=lambda ref_obj, _ct_id, _tmpl_map: f"{ref_obj.name}::display",
        ):
            ctx = build_display_template_context(obj)

        self.assertEqual(
            ctx["target"],
            "HTTPS::display, erp-user-url::display",
        )

    def test_multiobject_field_falls_back_to_str_on_lookup_error(self):
        obj = SimpleNamespace(
            _field_objects={
                "target": {
                    "name": "target",
                    "field": SimpleNamespace(type="multiobject"),
                }
            },
            target=_RelManager([_RefObject("HTTPS"), _RefObject("erp-user-url")]),
        )

        with patch(
            "django.contrib.contenttypes.models.ContentType.objects.get_for_model",
            side_effect=RuntimeError("boom"),
        ):
            ctx = build_display_template_context(obj)

        self.assertEqual(ctx["target"], "HTTPS, erp-user-url")
