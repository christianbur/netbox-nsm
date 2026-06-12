"""Tests for pre-filled index on COT rulebook rule add forms."""

import uuid

from django.urls import reverse

from utilities.testing import TestCase

from netbox_nsm.rulebooks.cot_rule_index import next_rulebook_index
from netbox_nsm.rulebooks.templates import RULEBOOK_GROUP


class NextRulebookIndexTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField

        slug = f"nsm_rb_idx_{uuid.uuid4().hex[:8]}"
        cls.cot = CustomObjectType.objects.create(
            name=slug,
            slug=slug,
            verbose_name="Index Prefill Test",
            group_name=RULEBOOK_GROUP,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.cot,
            name="index",
            label="Index",
            type="integer",
            primary=True,
            required=True,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.cot,
            name="name",
            label="Name",
            type="text",
            required=True,
        )
        cls.model = cls.cot.get_model()

    def test_next_index_empty_rulebook(self):
        self.assertEqual(next_rulebook_index(self.cot), 1)

    def test_next_index_after_demo_style_rules(self):
        self.model.objects.create(index=1, name="rule-a")
        self.model.objects.create(index=2, name="rule-b")
        self.assertEqual(next_rulebook_index(self.cot), 3)


class CotRuleAddIndexFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField

        slug = f"nsm_rb_add_idx_{uuid.uuid4().hex[:8]}"
        cls.cot = CustomObjectType.objects.create(
            name=slug,
            slug=slug,
            verbose_name="Add Index Prefill Test",
            group_name=RULEBOOK_GROUP,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.cot,
            name="index",
            label="Index",
            type="integer",
            primary=True,
            required=True,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.cot,
            name="name",
            label="Name",
            type="text",
            required=True,
        )
        cls.model = cls.cot.get_model()
        cls.model.objects.create(index=1, name="existing")

    def _add_url(self):
        return reverse(
            "plugins:netbox_custom_objects:customobject_add",
            kwargs={"custom_object_type": self.cot.slug},
        )

    def _edit_url(self, pk):
        return reverse(
            "plugins:netbox_custom_objects:customobject_edit",
            kwargs={"custom_object_type": self.cot.slug, "pk": pk},
        )

    def test_add_form_prefills_next_index(self):
        self.add_permissions(
            f"netbox_custom_objects.view_{self.model._meta.model_name}",
            f"netbox_custom_objects.add_{self.model._meta.model_name}",
        )
        response = self.client.get(self._add_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="index"')
        self.assertContains(response, 'id="id_index"')
        self.assertContains(response, 'value="2"')

    def test_add_form_respects_index_query_param(self):
        self.add_permissions(
            f"netbox_custom_objects.view_{self.model._meta.model_name}",
            f"netbox_custom_objects.add_{self.model._meta.model_name}",
        )
        response = self.client.get(self._add_url(), {"index": "99"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="99"')
        self.assertNotContains(response, 'value="2"')

    def test_edit_form_does_not_override_index(self):
        rule = self.model.objects.get(index=1)
        self.add_permissions(
            f"netbox_custom_objects.view_{self.model._meta.model_name}",
            f"netbox_custom_objects.change_{self.model._meta.model_name}",
        )
        response = self.client.get(self._edit_url(rule.pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="1"')
        self.assertNotContains(response, 'value="2"')

    def test_non_rulebook_cot_add_form_has_no_prefill(self):
        from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField

        slug = f"nsm_zone_{uuid.uuid4().hex[:8]}"
        cot = CustomObjectType.objects.create(
            name="Zone Test",
            slug=slug,
            verbose_name_plural="Zones",
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cot,
            name="index",
            label="Index",
            type="integer",
            primary=True,
            required=True,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cot,
            name="name",
            label="Name",
            type="text",
            required=True,
        )
        model = cot.get_model()
        model.objects.create(index=5, name="z1")

        self.add_permissions(
            f"netbox_custom_objects.view_{model._meta.model_name}",
            f"netbox_custom_objects.add_{model._meta.model_name}",
        )
        response = self.client.get(
            reverse(
                "plugins:netbox_custom_objects:customobject_add",
                kwargs={"custom_object_type": cot.slug},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'value="15"')

    def test_add_form_clone_prefills_from_copy_from(self):
        self.model.objects.create(index=2, name="source-rule")
        self.add_permissions(
            f"netbox_custom_objects.view_{self.model._meta.model_name}",
            f"netbox_custom_objects.add_{self.model._meta.model_name}",
        )
        source = self.model.objects.get(name="source-rule")
        response = self.client.get(self._add_url(), {"copy_from": source.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="3"')
        self.assertContains(response, "Copy of source-rule")

    def test_rules_actions_dropdown_includes_clone_link(self):
        from netbox_nsm.rulebooks.rules_tab_base import _render_actions_cell_html

        html = _render_actions_cell_html(
            "/edit/",
            "/delete/",
            "/add/?copy_from=5",
            can_change=True,
            can_delete=True,
            can_add=True,
        )
        self.assertIn("nsm-ag-action-clone", html)
        self.assertIn("copy_from=5", html)
