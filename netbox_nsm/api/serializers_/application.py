from django.contrib.contenttypes.models import ContentType
from rest_framework.serializers import (
    HyperlinkedIdentityField,
    SerializerMethodField,
    JSONField,
    ChoiceField,
    ListField,
    IntegerField,
)
from drf_spectacular.utils import extend_schema_field
from netbox.api.fields import ContentTypeField
from netbox.api.serializers import NetBoxModelSerializer, PrimaryModelSerializer
from utilities.api import get_serializer_for_model
from tenancy.api.serializers import TenantSerializer
from netbox_nsm.models import Application
from netbox_nsm.api.serializers import ApplicationItemSerializer
from netbox_nsm.constants import APPLICATION_ASSIGNMENT_MODELS
from netbox_nsm.choices import ProtocolChoices


class ApplicationSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:application-detail"
    )
    tenant = TenantSerializer(nested=True, required=False, allow_null=True)
    application_items = ApplicationItemSerializer(
        nested=True, required=False, allow_null=True, many=True
    )
    protocol = ListField(
        child=ChoiceField(choices=ProtocolChoices, required=False, allow_null=True),
        required=False,
        default=[],
    )
    source_ports = ListField(
        child=IntegerField(),
        required=False,
        allow_empty=True,
        default=[],
    )
    destination_ports = ListField(
        child=IntegerField(),
        required=False,
        allow_empty=True,
        default=[],
    )

    class Meta:
        model = Application
        fields = (
            "id",
            "url",
            "display",
            "name",
            "identifier",
            "category",
            "subcategory",
            "application_items",
            "standard_ports_text",
            "technology",
            "reference",
            "protocol",
            "destination_ports",
            "source_ports",
            "description",
            "tenant",
            "comments",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        brief_fields = (
            "id",
            "url",
            "display",
            "name",
            "identifier",
            "category",
            "subcategory",
            "application_items",
            "standard_ports_text",
            "technology",
            "reference",
            "protocol",
            "destination_ports",
            "source_ports",
            "description",
        )

    def create(self, validated_data):
        items = validated_data.pop("application_items", None)
        obj = super().create(validated_data)
        if items is not None:
            obj.application_items.set(items)
        return obj

    def update(self, instance, validated_data):
        items = validated_data.pop("application_items", None)
        obj = super().update(instance, validated_data)
        if items is not None:
            obj.application_items.set(items)
        return obj


