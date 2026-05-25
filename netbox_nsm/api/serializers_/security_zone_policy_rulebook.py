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
    AddressListSerializer,
    ApplicationSerializer,
    ApplicationSetSerializer,
    SecurityZoneSerializer,
    SecurityZoneRoleSerializer,
)
from netbox_nsm.constants import RULESET_ASSIGNMENT_MODELS
from netbox_nsm.models import (
    RulebookTypeChoices,
    SecurityZonePolicyRule,
    SecurityZonePolicyRulebook,
    SecurityZonePolicyRulebookAssignment,
)
from users.models import User


class NestedUserSerializer(PrimaryModelSerializer):
    class Meta:
        model = User
        fields = ("id", "url", "display", "username", "name")
        brief_fields = ("id", "url", "display", "username", "name")


class SecurityZonePolicyRulebookSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:securityzonepolicyrulebook-detail"
    )

    roles = SecurityZoneRoleSerializer(many=True, nested=True, required=False)

    class Meta:
        model = SecurityZonePolicyRulebook
        fields = (
            "id",
            "url",
            "display",
            "name",
            "rulebook_type",
            "roles",
            "description",
            "comments",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        brief_fields = ("id", "url", "display", "name", "rulebook_type", "roles")

    def create(self, validated_data):
        roles = validated_data.pop("roles", None)
        if roles is not None and len(roles) > 1:
            raise ValidationError(
                {"roles": ["Exactly one Security Zone Role may be set."]}
            )
        obj = super().create(validated_data)
        if roles is not None:
            obj.roles.set(roles)
        return obj

    def update(self, instance, validated_data):
        roles = validated_data.pop("roles", None)
        effective_type = validated_data.get("rulebook_type", instance.rulebook_type)
        effective_roles = roles if roles is not None else instance.roles.all()
        if effective_type == RulebookTypeChoices.MATRIX and not effective_roles:
            raise ValidationError(
                {"roles": ["Security Zone Roles are required when Rulebook Type is Security Matrix."]}
            )
        if effective_type == RulebookTypeChoices.MATRIX and len(effective_roles) != 1:
            raise ValidationError(
                {"roles": ["Exactly one Security Zone Role must be set for Security Matrix."]}
            )
        if roles is not None and len(roles) > 1:
            raise ValidationError(
                {"roles": ["Exactly one Security Zone Role may be set."]}
            )
        obj = super().update(instance, validated_data)
        if roles is not None:
            obj.roles.set(roles)
        return obj


class SecurityZonePolicyRuleSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:securityzonepolicyrule-detail"
    )
    rulebook = SecurityZonePolicyRulebookSerializer(nested=True, required=True)
    source_zones = SecurityZoneSerializer(nested=True, required=False, many=True)
    source_addresses = AddressListSerializer(nested=True, required=False, many=True)
    source_users = NestedUserSerializer(nested=True, required=False, many=True)
    destination_zones = SecurityZoneSerializer(nested=True, required=False, many=True)
    destination_addresses = AddressListSerializer(nested=True, required=False, many=True)
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
            "source_addresses",
            "source_users",
            "destination_groups",
            "destination_zones",
            "destination_addresses",
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
        source_addresses = validated_data.pop("source_addresses", None)
        source_users = validated_data.pop("source_users", None)
        destination_zones = validated_data.pop("destination_zones", None)
        destination_addresses = validated_data.pop("destination_addresses", None)
        destination_users = validated_data.pop("destination_users", None)
        applications = validated_data.pop("applications", None)
        application_sets = validated_data.pop("application_sets", None)

        obj = super().create(validated_data)
        if source_zones is not None:
            obj.source_zones.set(source_zones)
        if source_addresses is not None:
            obj.source_addresses.set(source_addresses)
        if source_users is not None:
            obj.source_users.set(source_users)
        if destination_zones is not None:
            obj.destination_zones.set(destination_zones)
        if destination_addresses is not None:
            obj.destination_addresses.set(destination_addresses)
        if destination_users is not None:
            obj.destination_users.set(destination_users)
        if applications is not None:
            obj.applications.set(applications)
        if application_sets is not None:
            obj.application_sets.set(application_sets)
        return obj

    def update(self, instance, validated_data):
        source_zones = validated_data.pop("source_zones", None)
        source_addresses = validated_data.pop("source_addresses", None)
        source_users = validated_data.pop("source_users", None)
        destination_zones = validated_data.pop("destination_zones", None)
        destination_addresses = validated_data.pop("destination_addresses", None)
        destination_users = validated_data.pop("destination_users", None)
        applications = validated_data.pop("applications", None)
        application_sets = validated_data.pop("application_sets", None)

        obj = super().update(instance, validated_data)
        if source_zones is not None:
            obj.source_zones.set(source_zones)
        if source_addresses is not None:
            obj.source_addresses.set(source_addresses)
        if source_users is not None:
            obj.source_users.set(source_users)
        if destination_zones is not None:
            obj.destination_zones.set(destination_zones)
        if destination_addresses is not None:
            obj.destination_addresses.set(destination_addresses)
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
