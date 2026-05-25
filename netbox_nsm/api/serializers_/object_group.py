from django.contrib.contenttypes.models import ContentType
from drf_spectacular.utils import extend_schema_field
from rest_framework.serializers import (
    HyperlinkedIdentityField,
    SerializerMethodField,
    JSONField,
)

from netbox.api.fields import ContentTypeField
from netbox.api.serializers import NetBoxModelSerializer, PrimaryModelSerializer
from utilities.api import get_serializer_for_model

from netbox_nsm.api.serializers_.address import AddressSerializer
from netbox_nsm.api.serializers_.application_item import ApplicationItemSerializer
from netbox_nsm.api.serializers_.application import ApplicationSerializer
from netbox_nsm.api.serializers_.securityzone import SecurityZoneSerializer
from netbox_nsm.models import ObjectGroup
from netbox_nsm.constants import OBJECT_ASSIGNMENT_MODELS


class ObjectGroupSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:objectgroup-detail"
    )
    addresses = AddressSerializer(nested=True, required=False, many=True)
    services = ApplicationItemSerializer(nested=True, required=False, many=True)
    applications = ApplicationSerializer(nested=True, required=False, many=True)
    zones = SecurityZoneSerializer(nested=True, required=False, many=True)

    class Meta:
        model = ObjectGroup
        fields = (
            "id",
            "url",
            "display",
            "name",
            "group_type",
            "addresses",
            "services",
            "applications",
            "zones",
            "description",
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
            "group_type",
        )

    def create(self, validated_data):
        addresses = validated_data.pop("addresses", None)
        services = validated_data.pop("services", None)
        applications = validated_data.pop("applications", None)
        zones = validated_data.pop("zones", None)

        obj = super().create(validated_data)
        if addresses is not None:
            obj.addresses.set(addresses)
        if services is not None:
            obj.services.set(services)
        if applications is not None:
            obj.applications.set(applications)
        if zones is not None:
            obj.zones.set(zones)
        return obj

    def update(self, instance, validated_data):
        addresses = validated_data.pop("addresses", None)
        services = validated_data.pop("services", None)
        applications = validated_data.pop("applications", None)
        zones = validated_data.pop("zones", None)

        obj = super().update(instance, validated_data)
        if addresses is not None:
            obj.addresses.set(addresses)
        if services is not None:
            obj.services.set(services)
        if applications is not None:
            obj.applications.set(applications)
        if zones is not None:
            obj.zones.set(zones)
        return obj


