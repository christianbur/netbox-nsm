"""Tests for COT rulebook parent/child hierarchy."""

from types import SimpleNamespace

from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from utilities.testing import TestCase

from netbox_nsm.models import CotRulebook
from netbox_nsm.rulebooks.cot_hierarchy import collect_descendant_slugs, validate_cot_parent_slug
from netbox_nsm.rulebooks.hierarchy import cot_rulebook_tree_order, hierarchy_depth, render_hierarchy_marker
from netbox_nsm.rulebooks.virtual_cot import VirtualCotRulebook


def _virtual_row(slug: str, name: str, *, parent_slug: str = "") -> VirtualCotRulebook:
    cot = SimpleNamespace(
        pk=1,
        slug=slug,
        verbose_name=name,
        name=name,
        description="",
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
    def test_model_rejects_self_parent(self):
        record = CotRulebook(slug="nsm_rb_demo", parent_slug="nsm_rb_demo")
        with self.assertRaises(ValidationError):
            record.full_clean()


class CotRulebookHierarchyFormTests(SimpleTestCase):
    def test_create_form_has_parent_field(self):
        from netbox_nsm.rulebooks.forms.cot import CotRulebookCreateForm

        with patch(
            "netbox_nsm.rulebooks.forms.cot.deployed_rulebook_parent_choices",
            return_value=[("", "—")],
        ):
            form = CotRulebookCreateForm()
        self.assertIn("parent_slug", form.fields)
        self.assertEqual(str(form.fields["parent_slug"].label), "Parent rulebook")
