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
from netbox_nsm.api.serializers_.object_label import ObjectLabelSerializer
from netbox_nsm.api.serializers_.object_sgt import ObjectSGTSerializer
from netbox_nsm.api.serializers_.object_user import ObjectUserSerializer
from netbox_nsm.api.serializers_.securityzone import SecurityZoneSerializer
from netbox_nsm.models import ObjectGroup, ObjectGroupAssignment
from netbox_nsm.constants import OBJECT_ASSIGNMENT_MODELS


class ObjectGroupSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:objectgroup-detail"
    )
    addresses = AddressSerializer(nested=True, required=False, many=True)
    services = ApplicationItemSerializer(nested=True, required=False, many=True)
    applications = ApplicationSerializer(nested=True, required=False, many=True)
    labels = ObjectLabelSerializer(nested=True, required=False, many=True)
    zones = SecurityZoneSerializer(nested=True, required=False, many=True)
    sgts = ObjectSGTSerializer(nested=True, required=False, many=True)
    users = ObjectUserSerializer(nested=True, required=False, many=True)

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
            "labels",
            "zones",
            "sgts",
            "users",
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
        labels = validated_data.pop("labels", None)
        zones = validated_data.pop("zones", None)
        sgts = validated_data.pop("sgts", None)
        users = validated_data.pop("users", None)

        obj = super().create(validated_data)
        if addresses is not None:
            obj.addresses.set(addresses)
        if services is not None:
            obj.services.set(services)
        if applications is not None:
            obj.applications.set(applications)
        if labels is not None:
            obj.labels.set(labels)
        if zones is not None:
            obj.zones.set(zones)
        if sgts is not None:
            obj.sgts.set(sgts)
        if users is not None:
            obj.users.set(users)
        return obj

    def update(self, instance, validated_data):
        addresses = validated_data.pop("addresses", None)
        services = validated_data.pop("services", None)
        applications = validated_data.pop("applications", None)
        labels = validated_data.pop("labels", None)
        zones = validated_data.pop("zones", None)
        sgts = validated_data.pop("sgts", None)
        users = validated_data.pop("users", None)

        obj = super().update(instance, validated_data)
        if addresses is not None:
            obj.addresses.set(addresses)
        if services is not None:
            obj.services.set(services)
        if applications is not None:
            obj.applications.set(applications)
        if labels is not None:
            obj.labels.set(labels)
        if zones is not None:
            obj.zones.set(zones)
        if sgts is not None:
            obj.sgts.set(sgts)
        if users is not None:
            obj.users.set(users)
        return obj


class ObjectGroupAssignmentSerializer(NetBoxModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:objectgroupassignment-detail"
    )
    group = ObjectGroupSerializer(nested=True, required=True, allow_null=False)
    assigned_object_type = ContentTypeField(
        queryset=ContentType.objects.filter(OBJECT_ASSIGNMENT_MODELS)
    )
    assigned_object = SerializerMethodField(read_only=True)

    class Meta:
        model = ObjectGroupAssignment
        fields = [
            "id",
            "url",
            "display",
            "group",
            "assigned_object_type",
            "assigned_object_id",
            "assigned_object",
            "created",
            "last_updated",
        ]
        brief_fields = (
            "id",
            "url",
            "display",
            "group",
            "assigned_object_type",
            "assigned_object_id",
        )

    @extend_schema_field(JSONField(allow_null=True))
    def get_assigned_object(self, obj):
        if obj.assigned_object is None:
            return None
        serializer = get_serializer_for_model(obj.assigned_object)
        context = {"request": self.context["request"]}
        return serializer(obj.assigned_object, nested=True, context=context).data
