from django.contrib.contenttypes.models import ContentType
from drf_spectacular.utils import extend_schema_field
from rest_framework.serializers import (
    HyperlinkedIdentityField,
    JSONField,
    SerializerMethodField,
    ValidationError,
)

from netbox.api.fields import ContentTypeField
from netbox.api.serializers import NetBoxModelSerializer, PrimaryModelSerializer
from utilities.api import get_serializer_for_model

from netbox_nsm.api.serializers import (
    ApplicationSerializer,
    ApplicationSetSerializer,
    SecurityZoneSerializer,
)
from netbox_nsm.constants import RULESET_ASSIGNMENT_MODELS
from netbox_nsm.models import (
    SecurityZonePolicyRule,
    SecurityZonePolicyRulebook,
    SecurityZonePolicyRulebookAssignment,
)
from users.models import User


class NestedUserSerializer(PrimaryModelSerializer):
    class Meta:
        model = User
        fields = ("id", "url", "display", "username")
        brief_fields = ("id", "url", "display", "username")


class SecurityZonePolicyRulebookSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:securityzonepolicyrulebook-detail"
    )

    class Meta:
        model = SecurityZonePolicyRulebook
        fields = (
            "id",
            "url",
            "display",
            "name",
            "rulebook_type",
            "description",
            "comments",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        brief_fields = ("id", "url", "display", "name", "rulebook_type")


class SecurityZonePolicyRuleSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:securityzonepolicyrule-detail"
    )
    rulebook = SecurityZonePolicyRulebookSerializer(nested=True, required=True)
    source_zones = SecurityZoneSerializer(nested=True, required=False, many=True)
    source_users = NestedUserSerializer(nested=True, required=False, many=True)
    destination_zones = SecurityZoneSerializer(nested=True, required=False, many=True)
    destination_users = NestedUserSerializer(nested=True, required=False, many=True)
    applications = ApplicationSerializer(nested=True, required=False, many=True)
    application_sets = ApplicationSetSerializer(nested=True, required=False, many=True)

    class Meta:
        model = SecurityZonePolicyRule
        fields = (
            "id",
            "url",
            "display",
            "rulebook",
            "index",
            "enabled",
            "name",
            "policy_action",
            "source_groups",
            "source_zones",
            "source_users",
            "destination_groups",
            "destination_zones",
            "destination_users",
            "services",
            "applications",
            "application_sets",
            "object_nat",
            "object_interface",
            "object_filter",
            "object_policer",
            "object_comment",
            "object_installed_on",
            "log_enabled",
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
            "rulebook",
            "index",
            "enabled",
            "name",
            "policy_action",
        )

    def create(self, validated_data):
        source_zones = validated_data.pop("source_zones", None)
        source_users = validated_data.pop("source_users", None)
        destination_zones = validated_data.pop("destination_zones", None)
        destination_users = validated_data.pop("destination_users", None)
        applications = validated_data.pop("applications", None)
        application_sets = validated_data.pop("application_sets", None)

        obj = super().create(validated_data)
        if source_zones is not None:
            obj.source_zones.set(source_zones)
        if source_users is not None:
            obj.source_users.set(source_users)
        if destination_zones is not None:
            obj.destination_zones.set(destination_zones)
        if destination_users is not None:
            obj.destination_users.set(destination_users)
        if applications is not None:
            obj.applications.set(applications)
        if application_sets is not None:
            obj.application_sets.set(application_sets)
        return obj

    def update(self, instance, validated_data):
        source_zones = validated_data.pop("source_zones", None)
        source_users = validated_data.pop("source_users", None)
        destination_zones = validated_data.pop("destination_zones", None)
        destination_users = validated_data.pop("destination_users", None)
        applications = validated_data.pop("applications", None)
        application_sets = validated_data.pop("application_sets", None)

        obj = super().update(instance, validated_data)
        if source_zones is not None:
            obj.source_zones.set(source_zones)
        if source_users is not None:
            obj.source_users.set(source_users)
        if destination_zones is not None:
            obj.destination_zones.set(destination_zones)
        if destination_users is not None:
            obj.destination_users.set(destination_users)
        if applications is not None:
            obj.applications.set(applications)
        if application_sets is not None:
            obj.application_sets.set(application_sets)
        return obj


class SecurityZonePolicyRulebookAssignmentSerializer(NetBoxModelSerializer):
    rulebook = SecurityZonePolicyRulebookSerializer(nested=True, required=True)
    assigned_object_type = ContentTypeField(
        queryset=ContentType.objects.filter(RULESET_ASSIGNMENT_MODELS)
    )
    assigned_object = SerializerMethodField(read_only=True)

    class Meta:
        model = SecurityZonePolicyRulebookAssignment
        fields = [
            "id",
            "url",
            "display",
            "rulebook",
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
            "rulebook",
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
