"""GET prefill for nsm_object_link Custom Object add forms."""

from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse
from utilities.querydict import normalize_querydict
from utilities.testing import TestCase

from netbox_nsm.security.links.cot_link_schema import get_object_link_cot
from netbox_nsm.security.links.object_link_service import get_object_link_model
from netbox_nsm.security.object_link_cot_form import (
    OBJECT_LINK_NETBOX_FIELD_LABEL,
    OBJECT_LINK_SECURITY_FIELD_LABEL,
    apply_object_link_add_prefill,
    apply_object_link_form_labels,
    sync_object_link_field_labels,
)
from netbox_nsm.tests.nsm_prerequisites import ensure_nsm_prerequisites


class ApplyObjectLinkAddPrefillTests(SimpleTestCase):
    def setUp(self):
        self.cot = type("COT", (), {"slug": "object_links"})()
        patcher = patch(
            "netbox_nsm.security.object_link_cot_form.is_link_table_cot",
            return_value=True,
        )
        self._link_table = patcher.start()
        self.addCleanup(patcher.stop)

    def test_maps_ct_id_and_obj_id_to_netbox_object(self):
        initial = {
            "ct_id": "12",
            "obj_id": "34",
            "return_url": "/devices/1/",
        }
        apply_object_link_add_prefill(self.cot, initial)
        self.assertNotIn("ct_id", initial)
        self.assertNotIn("obj_id", initial)
        self.assertEqual(initial["netbox_object__ct"], "12")
        self.assertEqual(initial["netbox_object__obj"], "34")
        self.assertEqual(initial["return_url"], "/devices/1/")

    def test_maps_legacy_object_a_params(self):
        initial = {
            "object_a_type_id": "5",
            "object_a_id": "99",
        }
        apply_object_link_add_prefill(self.cot, initial)
        self.assertNotIn("object_a_type_id", initial)
        self.assertNotIn("object_a_id", initial)
        self.assertEqual(initial["netbox_object__ct"], "5")
        self.assertEqual(initial["netbox_object__obj"], "99")

    def test_prefers_ct_id_over_object_a_type_id(self):
        initial = {
            "ct_id": "1",
            "object_a_type_id": "2",
            "obj_id": "3",
            "object_a_id": "4",
        }
        apply_object_link_add_prefill(self.cot, initial)
        self.assertEqual(initial["netbox_object__ct"], "1")
        self.assertEqual(initial["netbox_object__obj"], "3")

    @patch(
        "netbox_nsm.security.tab.eligibility.get_object_link_allowed_content_type_ids",
        return_value=(frozenset({12}), frozenset({272})),
    )
    def test_maps_security_only_ct_id_to_security_object(self, _ids):
        initial = {"ct_id": "272", "obj_id": "1", "name": "G-DNS"}
        apply_object_link_add_prefill(self.cot, initial)
        self.assertEqual(initial["security_object__ct"], "272")
        self.assertEqual(initial["security_object__obj"], "1")
        self.assertNotIn("netbox_object__ct", initial)

    def test_maps_object_b_params_to_security_object(self):
        initial = {
            "object_b_type_id": "77",
            "object_b_id": "88",
        }
        apply_object_link_add_prefill(self.cot, initial)
        self.assertNotIn("object_b_type_id", initial)
        self.assertNotIn("object_b_id", initial)
        self.assertEqual(initial["security_object__ct"], "77")
        self.assertEqual(initial["security_object__obj"], "88")

    def test_passes_through_comment(self):
        initial = {"comment": "panel note"}
        apply_object_link_add_prefill(self.cot, initial)
        self.assertEqual(initial["comments"], "panel note")
        self.assertNotIn("comment", initial)

    def test_defaults_status_to_active(self):
        initial = {}
        apply_object_link_add_prefill(self.cot, initial)
        self.assertEqual(initial["status"], "active")

    def test_preserves_explicit_status(self):
        initial = {"status": "planned"}
        apply_object_link_add_prefill(self.cot, initial)
        self.assertEqual(initial["status"], "planned")

    def test_does_not_overwrite_existing_subfields(self):
        initial = {
            "ct_id": "1",
            "obj_id": "2",
            "netbox_object__ct": "9",
            "netbox_object__obj": "8",
        }
        apply_object_link_add_prefill(self.cot, initial)
        self.assertEqual(initial["netbox_object__ct"], "9")
        self.assertEqual(initial["netbox_object__obj"], "8")

    def test_ignores_other_cot_slugs(self):
        initial = {"ct_id": "1", "obj_id": "2"}
        self._link_table.return_value = False
        apply_object_link_add_prefill(type("COT", (), {"slug": "nsm_zone"})(), initial)
        self.assertEqual(initial, {"ct_id": "1", "obj_id": "2"})


class ApplyObjectLinkFormLabelsTests(SimpleTestCase):
    def test_renames_poly_object_headings(self):
        from django import forms

        class _Form(forms.Form):
            netbox_object__ct = forms.IntegerField(label="Object A")
            netbox_object__obj = forms.IntegerField(label="Object A")
            security_object__ct = forms.IntegerField(label="Object B")
            security_object__obj = forms.IntegerField(label="Object B")

        form = _Form()
        form.custom_object_type_poly_obj_pairs = {
            "netbox_object__ct": ("netbox_object__obj", "Object A"),
            "security_object__ct": ("security_object__obj", "Object B"),
        }
        apply_object_link_form_labels(form)
        self.assertEqual(
            form.custom_object_type_poly_obj_pairs["netbox_object__ct"][1],
            str(OBJECT_LINK_NETBOX_FIELD_LABEL),
        )
        self.assertEqual(
            form.custom_object_type_poly_obj_pairs["security_object__ct"][1],
            str(OBJECT_LINK_SECURITY_FIELD_LABEL),
        )
        self.assertEqual(form.fields["netbox_object__ct"].label, OBJECT_LINK_NETBOX_FIELD_LABEL)
        self.assertEqual(form.fields["security_object__ct"].label, OBJECT_LINK_SECURITY_FIELD_LABEL)


class SyncObjectLinkFieldLabelsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        try:
            import netbox_custom_objects  # noqa: F401
        except ImportError:
            return
        ensure_nsm_prerequisites()

    def test_updates_deployed_cot_field_labels(self):
        try:
            from netbox_custom_objects.models import CustomObjectType
        except ImportError:
            self.skipTest("netbox_custom_objects not installed")
        cot = get_object_link_cot()
        if cot is None:
            self.skipTest("link-table COT not deployed")
        cot.fields.filter(name="netbox_object").update(label="Object A")
        cot.fields.filter(name="security_object").update(label="Object B")
        sync_object_link_field_labels()
        self.assertEqual(
            cot.fields.get(name="netbox_object").label,
            str(OBJECT_LINK_NETBOX_FIELD_LABEL),
        )
        self.assertEqual(
            cot.fields.get(name="security_object").label,
            str(OBJECT_LINK_SECURITY_FIELD_LABEL),
        )


class ObjectLinkCotAddFormPrefillTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        try:
            import netbox_custom_objects  # noqa: F401
        except ImportError:
            return
        ensure_nsm_prerequisites()
        cls.link_model = get_object_link_model()
        if cls.link_model is None:
            return

        from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Site
        from netbox_custom_objects.models import CustomObjectType

        site = Site.objects.create(name="OL Prefill Site", slug="ol-prefill-site")
        manufacturer = Manufacturer.objects.create(
            name="OL Prefill Mfr", slug="ol-prefill-mfr"
        )
        device_type = DeviceType.objects.create(
            manufacturer=manufacturer,
            model="OL Prefill Model",
            slug="ol-prefill-model",
        )
        role = DeviceRole.objects.create(name="OL Prefill Role", slug="ol-prefill-role")
        cls.device = Device.objects.create(
            name="ol-prefill-device",
            device_type=device_type,
            role=role,
            site=site,
            status="active",
        )
        cls.device_ct = ContentType.objects.get_for_model(Device)

        zone_cot = CustomObjectType.objects.filter(slug="nsm_zone").first()
        if zone_cot is None:
            return
        zone_model = zone_cot.get_model()
        cls.zone = zone_model.objects.create(name="ol-prefill-zone")
        cls.zone_ct = ContentType.objects.get_for_model(zone_model)

    def setUp(self):
        super().setUp()
        if get_object_link_model() is None:
            self.skipTest("nsm_object_link COT is not deployed")
        if not hasattr(self, "device"):
            self.skipTest("test prerequisites not created")

    def _add_url(self):
        from netbox_nsm.security.links.cot_link_schema import get_object_link_cot_slug

        slug = get_object_link_cot_slug()
        if slug is None:
            raise RuntimeError("link-table COT not deployed")
        return reverse(
            "plugins:netbox_custom_objects:customobject_add",
            kwargs={"custom_object_type": slug},
        )

    def test_add_form_prefills_from_query_params(self):
        from netbox_custom_objects.views import CustomObjectEditView

        link_model = get_object_link_model()
        self.add_permissions(
            f"netbox_custom_objects.view_{link_model._meta.model_name}",
            f"netbox_custom_objects.add_{link_model._meta.model_name}",
        )
        url = self._add_url()
        request = RequestFactory().get(
            url,
            {
                "ct_id": self.device_ct.pk,
                "obj_id": self.device.pk,
                "object_b_type_id": self.zone_ct.pk,
                "object_b_id": self.zone.pk,
                "comments": "prefilled note",
                "name": "ol-prefill-device → ol-prefill-zone",
                "status": "active",
            },
        )
        request.user = self.user
        view = CustomObjectEditView()
        link_cot = get_object_link_cot()
        if link_cot is None:
            self.skipTest("link-table COT not deployed")
        view.setup(request, custom_object_type=link_cot.slug)
        view.object = view.get_object()
        form_class = view.get_form(view.object._meta.model)
        form = form_class(
            instance=view.object,
            initial=normalize_querydict(request.GET),
        )
        self.assertEqual(form.initial.get("netbox_object__ct"), str(self.device_ct.pk))
        self.assertEqual(form.initial.get("netbox_object__obj"), str(self.device.pk))
        self.assertEqual(form.initial.get("security_object__ct"), str(self.zone_ct.pk))
        self.assertEqual(form.initial.get("security_object__obj"), str(self.zone.pk))
        self.assertEqual(form.initial.get("comments"), "prefilled note")
        self.assertEqual(form.initial.get("name"), "ol-prefill-device → ol-prefill-zone")
        self.assertEqual(form.initial.get("status"), "active")
