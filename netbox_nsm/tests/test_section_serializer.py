"""Section model REST/changelog serializer lookup."""

from django.test import TestCase

from netbox_nsm.api.serializers import SectionSerializer
from netbox_nsm.models import Section
from utilities.api import get_serializer_for_model


class SectionSerializerTests(TestCase):
    def test_get_serializer_for_model(self):
        self.assertIs(get_serializer_for_model(Section), SectionSerializer)

    def test_serialize_instance(self):
        section = Section.objects.create(
            slug="test-section",
            name="Test Section",
            sort_order=10,
        )
        data = SectionSerializer(section, context={"request": None}).data
        self.assertEqual(data["slug"], "test-section")
        self.assertEqual(data["name"], "Test Section")
        self.assertEqual(data["sort_order"], 10)
        self.assertEqual(data["custom_object_types"], [])
