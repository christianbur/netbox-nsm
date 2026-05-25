from django.contrib.contenttypes.models import ContentType
from rest_framework.serializers import (
    HyperlinkedIdentityField,
    SerializerMethodField,
    JSONField,
)
from drf_spectacular.utils import extend_schema_field
from netbox.api.fields import ContentTypeField
from netbox.api.serializers import NetBoxModelSerializer, PrimaryModelSerializer
from utilities.api import get_serializer_for_model
from tenancy.api.serializers import TenantSerializer
from netbox_nsm.models import ApplicationSet
from netbox_nsm.constants import APPLICATION_ASSIGNMENT_MODELS
from netbox_nsm.api.serializers import ApplicationSerializer


class NestedApplicationSetSerializer(NetBoxModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:applicationset-detail"
    )

    class Meta:
        model = ApplicationSet
        fields = (
            "id",
            "url",
            "display",
            "name",
            "identifier",
            "applications",
            "application_sets",
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
            "applications",
            "application_sets",
            "description",
        )


class ApplicationSetSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:applicationset-detail"
    )
    tenant = TenantSerializer(nested=True, required=False, allow_null=True)
    applications = ApplicationSerializer(
        nested=True, required=False, allow_null=True, many=True
    )
    application_sets = NestedApplicationSetSerializer(
        nested=True, required=False, allow_null=True, many=True
    )

    class Meta:
        model = ApplicationSet
        fields = (
            "id",
            "url",
            "display",
            "name",
            "identifier",
            "applications",
            "application_sets",
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
            "applications",
            "application_sets",
            "description",
        )

    def create(self, validated_data):
        applications = validated_data.pop("applications", None)
        application_sets = validated_data.pop("application_sets", None)
        obj = super().create(validated_data)
        if applications is not None:
            obj.applications.set(applications)
        if application_sets is not None:
            obj.application_sets.set(application_sets)
        return obj

    def update(self, instance, validated_data):
        applications = validated_data.pop("applications", None)
        application_sets = validated_data.pop("application_sets", None)
        obj = super().update(instance, validated_data)
        if applications is not None:
            obj.applications.set(applications)
        if application_sets is not None:
            obj.application_sets.set(application_sets)
        return obj


