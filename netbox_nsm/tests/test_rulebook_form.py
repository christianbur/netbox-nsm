"""Rulebook edit form behaviour."""

import json

from netbox_nsm.filtersets import RulebookFilterSet
from netbox_nsm.forms import RulebookForm
from netbox_nsm.models import Rulebook, RulebookStatusChoices, RulebookTypeChoices
from utilities.testing import TestCase


class RulebookFormParentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = Rulebook.objects.create(
            name="Root RB",
            rulebook_type=RulebookTypeChoices.SECURITY_RULES,
            status=RulebookStatusChoices.ACTIVE,
        )
        cls.child = Rulebook.objects.create(
            name="Child RB",
            rulebook_type=RulebookTypeChoices.SECURITY_RULES,
            status=RulebookStatusChoices.ACTIVE,
            parent=cls.root,
        )
        cls.grandchild = Rulebook.objects.create(
            name="Grandchild RB",
            rulebook_type=RulebookTypeChoices.SECURITY_RULES,
            status=RulebookStatusChoices.ACTIVE,
            parent=cls.child,
        )

    def test_parent_queryset_excludes_self_and_descendants(self):
        form = RulebookForm(instance=self.child)
        pks = set(form.fields["parent"].queryset.values_list("pk", flat=True))
        self.assertNotIn(self.child.pk, pks)
        self.assertNotIn(self.grandchild.pk, pks)
        self.assertIn(self.root.pk, pks)

    def test_parent_widget_excludes_self_via_api_param(self):
        form = RulebookForm(instance=self.child)
        static_params = json.loads(
            form.fields["parent"].widget.attrs.get("data-static-params", "[]")
        )
        excluded: set[int] = set()
        for entry in static_params:
            if entry.get("queryParam") != "id__n":
                continue
            value = entry["queryValue"]
            if isinstance(value, list):
                excluded.update(int(pk) for pk in value)
            else:
                excluded.add(int(value))
        self.assertIn(self.child.pk, excluded)
        self.assertIn(self.grandchild.pk, excluded)
        self.assertNotIn(self.root.pk, excluded)

    def test_rulebook_filterset_id_negation_excludes_pk(self):
        params = {"id__n": [self.child.pk]}
        qs = RulebookFilterSet(params, Rulebook.objects.all()).qs
        self.assertNotIn(self.child, qs)
        self.assertIn(self.root, qs)

    def test_clean_parent_rejects_self(self):
        form = RulebookForm(
            data={
                "name": self.child.name,
                "rulebook_type": self.child.rulebook_type,
                "status": self.child.status,
                "parent": self.child.pk,
                "matrix_tab_enabled": "1",
            },
            instance=self.child,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("parent", form.errors)
