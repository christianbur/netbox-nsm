from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.serializers import (
    HyperlinkedIdentityField,
    ModelSerializer,
    SerializerMethodField,
)
from netbox.api.fields import ContentTypeField
from netbox.api.serializers import NetBoxModelSerializer
from utilities.api import get_serializer_for_model

from netbox_nsm.models import (
    RulebookField,
    RulebookFieldType,
    SecurityPolicyRuleObjectItem,
    SecurityPolicyRuleGroupItem,
    SecurityPolicyRulebook,
    TypeConfig,
    SecurityObjectGroup,
)

__all__ = (
    "RulebookFieldSerializer",
    "RulebookFieldTypeSerializer",
    "SecurityPolicyRuleObjectItemSerializer",
    "SecurityPolicyRuleGroupItemSerializer",
)


# ── Nested helpers (no url needed, only used inside other serializers) ─────────

class _NestedRulebookSerializer(ModelSerializer):
    display = serializers.CharField(read_only=True)

    class Meta:
        model = SecurityPolicyRulebook
        fields = ("id", "display", "name")


class _NestedTypeConfigSerializer(ModelSerializer):
    display = serializers.CharField(read_only=True)
    content_type = ContentTypeField(read_only=True)

    class Meta:
        model = TypeConfig
        fields = ("id", "display", "content_type", "matching_class")


class _NestedGroupSerializer(ModelSerializer):
    display = serializers.CharField(read_only=True)

    class Meta:
        model = SecurityObjectGroup
        fields = ("id", "display", "name")


# ── RulebookField ──────────────────────────────────────────────────────────────

class RulebookFieldSerializer(ModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:rulebookfield-detail"
    )
    display = serializers.CharField(read_only=True)
    rulebook = _NestedRulebookSerializer(read_only=True)

    class Meta:
        model = RulebookField
        fields = (
            "id",
            "url",
            "display",
            "rulebook",
            "slug",
            "name",
            "sort_order",
            "placement",
        )
        brief_fields = ("id", "url", "display", "rulebook", "slug", "name", "placement")


# ── RulebookFieldType ──────────────────────────────────────────────────────────

class _NestedRulebookFieldSerializer(ModelSerializer):
    display = serializers.CharField(read_only=True)

    class Meta:
        model = RulebookField
        fields = ("id", "display", "slug", "name", "placement")


class RulebookFieldTypeSerializer(ModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:rulebookfieldtype-detail"
    )
    display = serializers.CharField(read_only=True)
    field = _NestedRulebookFieldSerializer(read_only=True)
    type_config = _NestedTypeConfigSerializer(read_only=True)

    class Meta:
        model = RulebookFieldType
        fields = (
            "id",
            "url",
            "display",
            "field",
            "type_config",
            "sort_order",
            "max_items",
        )
        brief_fields = ("id", "url", "display", "field", "type_config")


# ── SecurityPolicyRuleObjectItem ───────────────────────────────────────────────

class SecurityPolicyRuleObjectItemSerializer(ModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:securitypolicyruleobjectitem-detail"
    )
    display = serializers.CharField(read_only=True)
    content_type = ContentTypeField(read_only=True)
    assigned_object = SerializerMethodField(read_only=True)
    field = _NestedRulebookFieldSerializer(read_only=True)

    class Meta:
        model = SecurityPolicyRuleObjectItem
        fields = (
            "id",
            "url",
            "display",
            "rule",
            "field",
            "content_type",
            "object_id",
            "assigned_object",
            "exclude",
        )
        brief_fields = ("id", "url", "display", "rule", "field", "content_type", "object_id")

    @extend_schema_field({"type": "object"})
    def get_assigned_object(self, obj):
        serializer = get_serializer_for_model(obj.assigned_object)
        if serializer is None or obj.assigned_object is None:
            return None
        context = {"request": self.context.get("request")}
        return serializer(obj.assigned_object, nested=True, context=context).data


# ── SecurityPolicyRuleGroupItem ────────────────────────────────────────────────

class SecurityPolicyRuleGroupItemSerializer(ModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:securitypolicyrulegroupitem-detail"
    )
    display = serializers.CharField(read_only=True)
    security_group = _NestedGroupSerializer(read_only=True)
    field = _NestedRulebookFieldSerializer(read_only=True)

    class Meta:
        model = SecurityPolicyRuleGroupItem
        fields = (
            "id",
            "url",
            "display",
            "rule",
            "field",
            "security_group",
            "exclude",
        )
        brief_fields = ("id", "url", "display", "rule", "field", "security_group")
