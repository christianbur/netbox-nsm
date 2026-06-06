from django.contrib.contenttypes.models import ContentType
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
    Rule,
    RuleObjectItem,
    RuleGroupItem,
    Rulebook,
    TypeConfig,
    ObjectGroup,
)

__all__ = (
    "RulebookFieldSerializer",
    "RulebookFieldTypeSerializer",
    "RuleObjectItemSerializer",
    "RuleGroupItemSerializer",
)


# ── Nested helpers (no url needed, only used inside other serializers) ─────────


class _NestedRulebookSerializer(ModelSerializer):
    display = serializers.CharField(read_only=True)

    class Meta:
        model = Rulebook
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
        model = ObjectGroup
        fields = ("id", "display", "name")


# ── RulebookField ──────────────────────────────────────────────────────────────


class RulebookFieldSerializer(ModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:rulebookfield-detail"
    )
    display = serializers.CharField(read_only=True)
    rulebook = serializers.PrimaryKeyRelatedField(queryset=Rulebook.objects.all())

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
            "field_kind",
            "visible",
            "show_colored_pills",
            "searchable",
            "filterable",
            "facet_mode",
            "facet_weight",
            "max_visible_pills",
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
    field = serializers.PrimaryKeyRelatedField(queryset=RulebookField.objects.all())
    type_config = serializers.PrimaryKeyRelatedField(queryset=TypeConfig.objects.all())

    class Meta:
        model = RulebookFieldType
        fields = (
            "id",
            "url",
            "display",
            "field",
            "type_config",
            "sort_order",
            "visible",
            "max_items",
            "name_filter_regex",
        )
        brief_fields = ("id", "url", "display", "field", "type_config")


# ── RuleObjectItem ───────────────────────────────────────────────


class RuleObjectItemSerializer(ModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:ruleobjectitem-detail"
    )
    display = serializers.CharField(read_only=True)
    rule = serializers.PrimaryKeyRelatedField(queryset=Rule.objects.all())
    field = serializers.PrimaryKeyRelatedField(
        queryset=RulebookField.objects.all(), allow_null=True, required=False
    )
    content_type = ContentTypeField(queryset=ContentType.objects.all())
    assigned_object = SerializerMethodField(read_only=True)

    class Meta:
        model = RuleObjectItem
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
        brief_fields = (
            "id",
            "url",
            "display",
            "rule",
            "field",
            "content_type",
            "object_id",
        )

    @extend_schema_field({"type": "object"})
    def get_assigned_object(self, obj):
        serializer = get_serializer_for_model(obj.assigned_object)
        if serializer is None or obj.assigned_object is None:
            return None
        context = {"request": self.context.get("request")}
        return serializer(obj.assigned_object, nested=True, context=context).data


# ── RuleGroupItem ────────────────────────────────────────────────


class RuleGroupItemSerializer(ModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:rulegroupitem-detail"
    )
    display = serializers.CharField(read_only=True)
    rule = serializers.PrimaryKeyRelatedField(queryset=Rule.objects.all())
    field = serializers.PrimaryKeyRelatedField(
        queryset=RulebookField.objects.all(), allow_null=True, required=False
    )
    security_group = serializers.PrimaryKeyRelatedField(
        queryset=ObjectGroup.objects.all()
    )

    class Meta:
        model = RuleGroupItem
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
