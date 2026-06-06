"""Tests for explicit branch DB routing helpers."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.tests.branching_stubs import ensure_netbox_branching_stubs
from netbox_nsm.branch_db import (
    branch_aware_manager,
    branch_db_alias,
    branch_save_instance,
    db_alias_for_instance,
    detect_instance_db_alias,
    ensure_branch_context,
    pin_instance_db_alias,
    required_junction_db_alias,
    resolve_db_alias,
    use_db_alias,
)
from netbox_nsm.models import RuleObjectItem


class BranchDbTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        ensure_netbox_branching_stubs()
        super().setUpClass()

    def test_branch_db_alias_without_branching(self):
        self.assertIsNone(branch_db_alias())

    @patch("netbox_branching.contextvars.active_branch")
    def test_branch_db_alias_with_active_branch(self, active_branch):
        branch = MagicMock(schema_name="branch_k11eb2ac")
        active_branch.get.return_value = branch
        self.assertEqual(branch_db_alias(), "schema_branch_k11eb2ac")

    def test_resolve_db_alias_prefers_request_active_branch(self):
        branch = MagicMock(schema_name="branch_k11eb2ac")
        request = MagicMock(active_branch=branch)
        instance = MagicMock()
        instance._state.db = "default"
        self.assertEqual(
            resolve_db_alias(instance=instance, request=request),
            "schema_branch_k11eb2ac",
        )

    @patch("netbox_branching.models.Branch")
    def test_branch_from_request_query_param(self, Branch):
        from netbox_nsm.branch_db import _branch_from_request

        branch = MagicMock()
        branch.ready = True
        Branch.objects.get.return_value = branch
        request = MagicMock(active_branch=None)
        request.GET = {"_branch": "k11eb2ac"}
        request.COOKIES = {}
        self.assertIs(_branch_from_request(request), branch)
        Branch.objects.get.assert_called_once_with(schema_id="k11eb2ac")

    @patch("netbox_nsm.branch_db.branch_db_alias", return_value=None)
    def test_db_alias_for_instance_prefers_state_db(self, _alias):
        instance = MagicMock()
        instance._state.db = "schema_branch_hh"
        self.assertEqual(db_alias_for_instance(instance), "schema_branch_hh")

    @patch("netbox_nsm.branch_db.router_write_alias", return_value=None)
    @patch("netbox_nsm.branch_db.resolve_db_alias", return_value="schema_from_rule")
    def test_branch_aware_manager_uses_resolved_alias(self, _alias, _router):
        request = MagicMock()
        instance = MagicMock()
        mgr = branch_aware_manager(RuleObjectItem, instance, request)
        self.assertEqual(mgr.db, "schema_from_rule")
        _alias.assert_called_once_with(instance=instance, request=request)

    @patch("netbox_nsm.branch_db.resolve_db_alias", return_value="schema_test")
    def test_branch_save_instance(self, _alias):
        instance = MagicMock()
        request = MagicMock()
        branch_save_instance(instance, request=request, update_fields=["name"])
        instance.save.assert_called_once_with(
            using="schema_test", update_fields=["name"]
        )
        self.assertEqual(instance._state.db, "schema_test")

    def test_pin_instance_db_alias(self):
        branch = MagicMock(schema_name="branch_k11eb2ac")
        request = MagicMock(active_branch=branch)
        instance = MagicMock()
        instance._state.db = "default"
        pin_instance_db_alias(instance, request)
        self.assertEqual(instance._state.db, "schema_branch_k11eb2ac")

    @patch("netbox_branching.utilities.activate_branch")
    def test_ensure_branch_context_always_activates_from_request(self, activate_branch):
        branch = MagicMock()
        request = MagicMock(active_branch=branch)
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=None)
        cm.__exit__ = MagicMock(return_value=False)
        activate_branch.return_value = cm

        with ensure_branch_context(request):
            pass

        activate_branch.assert_called_once_with(branch)

    def test_use_db_alias_pins_resolve(self):
        with use_db_alias("schema_branch_k11eb2ac"):
            self.assertEqual(
                resolve_db_alias(),
                "schema_branch_k11eb2ac",
            )
        self.assertIsNone(resolve_db_alias())

    @patch("netbox_nsm.branch_db.router_write_alias", return_value="schema_from_router")
    @patch("netbox_nsm.branch_db.resolve_db_alias", return_value=None)
    def test_required_junction_db_alias_uses_router(self, _resolve, _router):
        from netbox_nsm.models import RuleObjectItem

        instance = MagicMock(pk=1)
        self.assertEqual(
            required_junction_db_alias(instance, None),
            "schema_from_router",
        )
        _router.assert_called_once_with(RuleObjectItem)

    @patch("netbox_nsm.branch_db.router_write_alias", return_value=None)
    @patch(
        "netbox_nsm.branch_db.detect_instance_db_alias",
        return_value="schema_branch_only",
    )
    @patch("netbox_nsm.branch_db.resolve_db_alias", return_value=None)
    def test_required_junction_db_alias_probes_instance(
        self, _resolve, _detect, _router
    ):
        from netbox_nsm.branch_db import required_junction_db_alias

        instance = MagicMock(pk=210)
        self.assertEqual(
            required_junction_db_alias(instance, None),
            "schema_branch_only",
        )

    @patch("netbox_nsm.branch_db._branch_from_request", return_value=None)
    @patch("netbox_nsm.branch_db.branch_db_alias", return_value=None)
    def test_detect_instance_db_alias_branch_only(self, _ctx, _req):
        instance = MagicMock()
        instance.pk = 204
        instance.__class__ = MagicMock()
        instance.__class__.objects.using.return_value.filter.return_value.exists.side_effect = [
            False,  # default
            True,  # schema_branch_hh
        ]

        with patch("netbox_branching.models.Branch") as Branch:
            branch = MagicMock()
            branch.ready = True
            branch.schema_name = "branch_hh"
            Branch.objects.all.return_value = [branch]

            self.assertEqual(
                detect_instance_db_alias(instance),
                "schema_branch_hh",
            )
