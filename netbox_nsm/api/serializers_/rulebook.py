from django.contrib.contenttypes.models import ContentType
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.serializers import (
    HyperlinkedIdentityField,
    JSONField,
    SerializerMethodField,
)

from netbox.api.fields import ContentTypeField
from netbox.api.serializers import NetBoxModelSerializer, PrimaryModelSerializer
from utilities.api import get_serializer_for_model

from netbox_nsm.constants import RULESET_ASSIGNMENT_MODELS
from netbox_nsm.models import Rule, Rulebook, RulebookAssignment
from users.models import User


class NestedUserSerializer(PrimaryModelSerializer):
    class Meta:
        model = User
        fields = ("id", "url", "display", "username")
        brief_fields = ("id", "url", "display", "username")


class RulebookSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:rulebook-detail"
    )
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Rulebook.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Rulebook
        fields = (
            "id",
            "url",
            "display",
            "name",
            "rulebook_type",
            "status",
            "parent",
            "platform",
            "mgmt_url",
            "rule_comment_template",
            "description",
            "comments",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        brief_fields = ("id", "url", "display", "name", "rulebook_type")

    def validate(self, attrs):
        from netbox_nsm.rulebook_hierarchy import validate_parent_choice

        if isinstance(attrs, Rulebook):
            return attrs

        attrs = super().validate(attrs)
        parent = attrs.get("parent")
        if "parent" in attrs:
            instance = getattr(self, "instance", None)
            error = validate_parent_choice(instance, parent)
            if error:
                raise serializers.ValidationError({"parent": error})
        return attrs


class RuleSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(view_name="plugins-api:netbox_nsm-api:rule-detail")
    rulebook = RulebookSerializer(nested=True, required=True)
    source_users = NestedUserSerializer(nested=True, required=False, many=True)
    destination_users = NestedUserSerializer(nested=True, required=False, many=True)

    class Meta:
        model = Rule
        fields = (
            "id",
            "url",
            "display",
            "rulebook",
            "index",
            "enabled",
            "name",
            "source_users",
            "destination_users",
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
        )


class RulebookAssignmentSerializer(NetBoxModelSerializer):
    rulebook = RulebookSerializer(nested=True, required=True)
    assigned_object_type = ContentTypeField(
        queryset=ContentType.objects.filter(RULESET_ASSIGNMENT_MODELS)
    )
    assigned_object = SerializerMethodField(read_only=True)

    class Meta:
        model = RulebookAssignment
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
