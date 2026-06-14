"""Tests for COT rulebook parent/child hierarchy."""

from types import SimpleNamespace

from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from utilities.testing import TestCase

from netbox_nsm.objects.rulebook_config import save_rulebook_config_for_cot
from netbox_nsm.rulebooks.cot_hierarchy import collect_descendant_slugs, validate_cot_parent_slug
from netbox_nsm.rulebooks.hierarchy import cot_rulebook_tree_order, hierarchy_depth, render_hierarchy_marker
from netbox_nsm.rulebooks.templates import RULEBOOK_GROUP
from netbox_nsm.rulebooks.virtual_cot import VirtualCotRulebook


def _virtual_row(slug: str, name: str, *, parent_slug: str = "") -> VirtualCotRulebook:
    fields = MagicMock()
    fields.values_list.return_value = []
    fields.order_by.return_value = []
    cot = SimpleNamespace(
        pk=1,
        slug=slug,
        verbose_name=name,
        name=name,
        description="",
        fields=fields,
    )
    row = VirtualCotRulebook(cot, rule_count=0)
    row.parent_slug = parent_slug
    return row


class CotRulebookHierarchyUnitTests(SimpleTestCase):
    def test_collect_descendant_slugs(self):
        parent_map = {
            "nsm_rb_child": "nsm_rb_root",
            "nsm_rb_grand": "nsm_rb_child",
        }
        self.assertEqual(
            collect_descendant_slugs("nsm_rb_root", parent_map=parent_map),
            {"nsm_rb_child", "nsm_rb_grand"},
        )

    @patch(
        "netbox_nsm.rulebooks.cot_hierarchy.get_deployed_cot_rulebook",
        return_value=object(),
    )
    def test_validate_parent_cycle(self, _mock):
        parent_map = {"nsm_rb_child": "nsm_rb_root"}
        self.assertIsNone(
            validate_cot_parent_slug(
                "nsm_rb_child",
                "nsm_rb_root",
                parent_map=parent_map,
            )
        )
        self.assertIsNotNone(
            validate_cot_parent_slug(
                "nsm_rb_root",
                "nsm_rb_child",
                parent_map=parent_map,
            )
        )

    def test_cot_rulebook_tree_order(self):
        root = _virtual_row("nsm_rb_a", "A")
        child = _virtual_row("nsm_rb_b", "B", parent_slug="nsm_rb_a")
        other = _virtual_row("nsm_rb_c", "C")
        ordered = cot_rulebook_tree_order([child, other, root])
        self.assertEqual([row.slug for row in ordered], ["nsm_rb_a", "nsm_rb_b", "nsm_rb_c"])

    def test_virtual_row_depth_and_marker(self):
        root = _virtual_row("nsm_rb_a", "A")
        child = _virtual_row("nsm_rb_b", "B")
        child.parent = root
        child.nsm_list_depth = hierarchy_depth(child)
        self.assertEqual(child.nsm_list_depth, 1)
        self.assertIn("record-depth", render_hierarchy_marker(child.nsm_list_depth))


class CotRulebookHierarchyModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from netbox_custom_objects.models import CustomObjectType

        cls.cot = CustomObjectType.objects.create(
            name="nsm_rb_demo",
            slug="nsm_rb_demo",
            verbose_name="Demo",
            description="",
            group_name=RULEBOOK_GROUP,
        )

    def test_save_rejects_self_parent(self):
        with self.assertRaises(ValidationError):
            save_rulebook_config_for_cot(
                self.cot,
                {"parent_slug": "nsm_rb_demo"},
            )


class CotRulebookHierarchyFormTests(SimpleTestCase):
    def test_parent_choices_include_none_option(self):
        from netbox_nsm.rulebooks.cot_hierarchy import deployed_rulebook_parent_choices

        with patch(
            "netbox_nsm.rulebooks.cot_hierarchy.iter_deployed_cot_rulebooks",
            return_value=[],
        ):
            choices = deployed_rulebook_parent_choices()
        self.assertEqual(choices[0], ("", "None"))

    def test_create_form_has_parent_field(self):
        from netbox_nsm.rulebooks.forms.cot import CotRulebookCreateForm

        with patch(
            "netbox_nsm.rulebooks.forms.cot.deployed_rulebook_parent_choices",
            return_value=[("", "—")],
        ):
            form = CotRulebookCreateForm()
        self.assertIn("parent_slug", form.fields)
        self.assertEqual(str(form.fields["parent_slug"].label), "Parent rulebook")

    def test_parent_slug_widget_uses_native_select(self):
        from netbox_nsm.rulebooks.forms.cot import CotRulebookCreateForm

        with patch(
            "netbox_nsm.rulebooks.forms.cot.deployed_rulebook_parent_choices",
            return_value=[("", "None")],
        ):
            form = CotRulebookCreateForm()
        classes = form.fields["parent_slug"].widget.attrs.get("class", "")
        self.assertIn("no-ts", classes)
