"""Tests for Object Link schema configuration service."""

from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from ipam.models import Prefix

from netbox_nsm.core.display_utils import ct_display_label
from netbox_nsm.security.object_link_config.service import (
    attach_link_usage_counts,
    apply_object_link_schema_changes,
    build_object_link_portable_document,
    content_type_to_portable_ref,
    get_object_link_config_state,
    portable_ref_to_content_type,
    preview_object_link_schema_changes,
    split_object_link_types,
)
from netbox_nsm.security.tab.eligibility import clear_object_link_eligibility_cache
from netbox_nsm.tests.nsm_prerequisites import ensure_nsm_prerequisites
from netbox_nsm.type_metadata.config import is_assignable_from_content_type
from utilities.testing import TestCase


class ObjectLinkConfigServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        try:
            import netbox_custom_objects  # noqa: F401
        except ImportError:
            return
        ensure_nsm_prerequisites()

    def setUp(self):
        clear_object_link_eligibility_cache()

    def test_portable_ref_roundtrip_prefix(self):
        ct = ContentType.objects.get_for_model(Prefix)
        ref = content_type_to_portable_ref(ct)
        self.assertEqual(ref, "ipam/prefix")
        self.assertEqual(portable_ref_to_content_type(ref).pk, ct.pk)

    def test_type_entry_uses_ct_display_label(self):
        ct = ContentType.objects.get_for_model(Prefix)
        ref = content_type_to_portable_ref(ct)
        state = get_object_link_config_state()
        if state is None:
            entries = [
                {
                    "ref": ref,
                    "label": "ignored",
                    "display_label": ct_display_label(ct),
                    "selected": True,
                }
            ]
        else:
            entries = [entry for entry in state["host_types"] if entry["ref"] == ref]
            if not entries:
                self.skipTest("prefix not in host candidates")
        self.assertEqual(entries[0]["display_label"], ct_display_label(ct))
        self.assertIn("›", entries[0]["display_label"])

    def test_split_object_link_types_orders_selected_and_available(self):
        entries = [
            {"ref": "b", "display_label": "Bravo", "selected": True},
            {"ref": "a", "display_label": "Alpha", "selected": False},
            {"ref": "c", "display_label": "Charlie", "selected": True},
        ]
        split = split_object_link_types(entries)
        self.assertEqual([entry["ref"] for entry in split["selected"]], ["b", "c"])
        self.assertEqual([entry["ref"] for entry in split["available"]], ["a"])

    def test_get_state_when_schema_deployed(self):
        try:
            import netbox_custom_objects  # noqa: F401
        except ImportError:
            self.skipTest("netbox_custom_objects not installed")
        state = get_object_link_config_state()
        if state is None:
            self.skipTest("nsm_object_link not deployed")
        self.assertIn("dcim/device", state["host_refs"])
        self.assertTrue(state["security_refs"])
        security_refs = {entry["ref"] for entry in state["security_types"]}
        self.assertNotIn("custom-objects/nsm_action", security_refs)

    def test_security_candidates_include_all_custom_objects(self):
        try:
            import netbox_custom_objects  # noqa: F401
        except ImportError:
            self.skipTest("netbox_custom_objects not installed")
        from netbox_nsm.tests.object_link_helpers import create_custom_object_instance

        state = get_object_link_config_state()
        if state is None:
            self.skipTest("nsm_object_link not deployed")

        custom_instance = create_custom_object_instance(name="Object link config picker test")
        custom_ref = content_type_to_portable_ref(
            ContentType.objects.get_for_model(custom_instance.__class__)
        )
        state = get_object_link_config_state()
        all_security_refs = {entry["ref"] for entry in state["security_types"]}
        self.assertIn(custom_ref, all_security_refs)

    def test_security_candidates_exclude_action(self):
        try:
            import netbox_custom_objects  # noqa: F401
        except ImportError:
            self.skipTest("netbox_custom_objects not installed")
        state = get_object_link_config_state()
        if state is None:
            self.skipTest("nsm_object_link not deployed")
        available = split_object_link_types(state["security_types"])["available"]
        self.assertFalse(any(entry["ref"] == "custom-objects/nsm_action" for entry in available))

    def test_host_candidates_use_public_object_types_not_code_whitelist(self):
        try:
            import netbox_custom_objects  # noqa: F401
        except ImportError:
            self.skipTest("netbox_custom_objects not installed")
        from dcim.models import Rack

        state = get_object_link_config_state()
        if state is None:
            self.skipTest("nsm_object_link not deployed")
        host_refs = set(state["host_refs"])
        rack_ref = content_type_to_portable_ref(ContentType.objects.get_for_model(Rack))
        all_host_refs = {entry["ref"] for entry in state["host_types"]}
        self.assertIn(rack_ref, all_host_refs)
        if rack_ref not in host_refs:
            available = split_object_link_types(state["host_types"])["available"]
            self.assertIn(rack_ref, {entry["ref"] for entry in available})

    def test_preview_unchanged_lists_no_impact(self):
        try:
            import netbox_custom_objects  # noqa: F401
        except ImportError:
            self.skipTest("netbox_custom_objects not installed")
        state = get_object_link_config_state()
        if state is None:
            self.skipTest("nsm_object_link not deployed")
        preview = preview_object_link_schema_changes(
            state["host_refs"],
            state["security_refs"],
        )
        self.assertEqual(preview["host_added"], [])
        self.assertEqual(preview["host_removed"], [])
        self.assertEqual(preview["security_added"], [])
        self.assertEqual(preview["security_removed"], [])
        self.assertFalse(preview["destructive"])

    def test_attach_link_usage_counts_marks_in_use_types(self):
        try:
            import netbox_custom_objects  # noqa: F401
        except ImportError:
            self.skipTest("netbox_custom_objects not installed")
        from dcim.models import Device

        state = get_object_link_config_state()
        if state is None:
            self.skipTest("nsm_object_link not deployed")
        if not hasattr(self, "device"):
            self.skipTest("prerequisites not created")

        device_ref = content_type_to_portable_ref(
            ContentType.objects.get_for_model(Device)
        )
        if device_ref not in state["host_refs"]:
            self.skipTest("device not configured as host type")

        from netbox_nsm.tests.object_link_helpers import create_custom_object_instance

        zone = create_custom_object_instance(name="Usage count zone")
        create_or_update = __import__(
            "netbox_nsm.security.links.object_link_service",
            fromlist=["create_or_update_links"],
        ).create_or_update_links
        create_or_update(self.device, zone, comment="usage count test")

        entries = [
            entry
            for entry in state["host_types"]
            if entry["ref"] == device_ref and entry.get("selected")
        ]
        if not entries:
            self.skipTest("device entry missing from host types")
        attach_link_usage_counts(entries, side="host")
        self.assertGreater(entries[0]["usage_count"], 0)
        self.assertFalse(entries[0]["can_remove"])

        unused_ref = content_type_to_portable_ref(ContentType.objects.get_for_model(Prefix))
        unused_entries = [
            {
                "ref": unused_ref,
                "content_type_id": ContentType.objects.get_for_model(Prefix).pk,
                "selected": True,
            }
        ]
        if unused_ref in state["host_refs"]:
            self.skipTest("prefix is selected in this install")
        attach_link_usage_counts(unused_entries, side="host")
        self.assertEqual(unused_entries[0]["usage_count"], 0)
        self.assertTrue(unused_entries[0]["can_remove"])

    def test_build_portable_document_updates_field_refs(self):
        doc = build_object_link_portable_document(
            ["ipam/prefix"],
            ["custom-objects/nsm_zone"],
        )
        type_def = doc["types"][0]
        fields = {f["name"]: f for f in type_def["fields"]}
        self.assertEqual(fields["netbox_object"]["related_object_types"], ["ipam/prefix"])
        self.assertEqual(
            fields["security_object"]["related_object_types"],
            ["custom-objects/nsm_zone"],
        )

    def test_apply_remove_unused_security_type(self):
        try:
            import netbox_custom_objects  # noqa: F401
        except ImportError:
            self.skipTest("netbox_custom_objects not installed")

        state = get_object_link_config_state()
        if state is None:
            self.skipTest("nsm_object_link not deployed")
        if len(state["security_refs"]) < 2:
            self.skipTest("need at least two security types")

        original_security = list(state["security_refs"])
        selected_entries = [
            entry
            for entry in state["security_types"]
            if entry.get("selected")
        ]
        attach_link_usage_counts(selected_entries, side="security")
        removable = [
            entry["ref"]
            for entry in selected_entries
            if entry.get("can_remove")
        ]
        if not removable:
            self.skipTest("no unused security type to remove")

        removed_ref = removable[0]
        new_security = [ref for ref in original_security if ref != removed_ref]

        try:
            preview = apply_object_link_schema_changes(
                state["host_refs"],
                new_security,
            )
            self.assertIn(removed_ref, preview["security_removed"])
            updated = get_object_link_config_state()
            self.assertNotIn(removed_ref, updated["security_refs"])
        finally:
            apply_object_link_schema_changes(
                state["host_refs"],
                original_security,
            )


class ObjectLinkConfigViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        try:
            import netbox_custom_objects  # noqa: F401
        except ImportError:
            return
        ensure_nsm_prerequisites()

    def test_edit_requires_view_permission(self):
        try:
            import netbox_custom_objects  # noqa: F401
        except ImportError:
            self.skipTest("netbox_custom_objects not installed")
        if get_object_link_config_state() is None:
            self.skipTest("nsm_object_link not deployed")

        url = reverse("plugins:netbox_nsm:object_link_config_edit")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        self.add_permissions("netbox_custom_objects.view_customobjecttype")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "object-link-config-panel")
        self.assertContains(response, "object-link-config-add-search")
        self.assertContains(response, "Quick search")
        self.assertContains(response, ct_display_label(ContentType.objects.get_for_model(Prefix)))

    def test_overview_uses_display_labels(self):
        try:
            import netbox_custom_objects  # noqa: F401
        except ImportError:
            self.skipTest("netbox_custom_objects not installed")
        state = get_object_link_config_state()
        if state is None:
            self.skipTest("nsm_object_link not deployed")

        self.add_permissions("netbox_custom_objects.view_customobjecttype")
        response = self.client.get(reverse("plugins:netbox_nsm:object_link_config"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "object-link-config-panel")
        self.assertContains(response, "Instances")
        prefix_label = ct_display_label(ContentType.objects.get_for_model(Prefix))
        if any(entry["ref"] == "ipam/prefix" for entry in state["host_types"] if entry["selected"]):
            self.assertContains(response, prefix_label)
        self.assertContains(response, "object-list")


class IsAssignableFromContentTypeTests(TestCase):
    def test_rejects_assigner_not_in_host_ids(self):
        prefix_ct = ContentType.objects.get_for_model(Prefix).pk
        zone_ct = 99999
        with patch(
            "netbox_nsm.security.tab.eligibility.get_object_link_allowed_content_type_ids",
            return_value=(frozenset({prefix_ct}), frozenset({zone_ct})),
        ), patch(
            "netbox_nsm.type_metadata.config.is_linkable_content_type",
            return_value=True,
        ):
            self.assertFalse(is_assignable_from_content_type(12345, zone_ct))

    def test_accepts_when_host_and_policy_match(self):
        prefix_ct = ContentType.objects.get_for_model(Prefix).pk
        zone_ct = 88888
        with patch(
            "netbox_nsm.security.tab.eligibility.get_object_link_allowed_content_type_ids",
            return_value=(frozenset({prefix_ct}), frozenset({zone_ct})),
        ), patch(
            "netbox_nsm.type_metadata.config.is_linkable_content_type",
            return_value=True,
        ):
            self.assertTrue(is_assignable_from_content_type(prefix_ct, zone_ct))
