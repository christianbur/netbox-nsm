from rest_framework import serializers

from netbox_nsm.core.display_template import (
    DEFAULT_DISPLAY_TEMPLATE,
    normalize_display_template,
    validate_display_template,
)
from netbox_nsm.type_metadata.config import _normalize_rule_view_columns

__all__ = (
    "NsmConfigDocumentSerializer",
    "NsmConfigRuleViewSerializer",
    "NsmConfigRulebookSerializer",
)


class NsmConfigRuleViewSerializer(serializers.Serializer):
    class ColumnSerializer(serializers.Serializer):
        key = serializers.CharField(required=False, allow_blank=True)
        label = serializers.CharField(required=True, allow_blank=False)
        column_order = serializers.IntegerField(required=False, min_value=0)
        sort_order = serializers.IntegerField(required=False, min_value=0)
        value_template = serializers.CharField(required=True, allow_blank=False)

    sort_order = serializers.IntegerField(min_value=0, required=False, default=0)
    display_template = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default=DEFAULT_DISPLAY_TEMPLATE,
    )
    columns = ColumnSerializer(many=True, required=False, default=list)

    def validate_display_template(self, value):
        tmpl = normalize_display_template(value)
        validate_display_template(tmpl)
        return tmpl

    def validate_columns(self, value):
        normalized = _normalize_rule_view_columns(value or [])
        if value and not normalized:
            raise serializers.ValidationError(
                "Each column must define at least 'label' and 'value_template'."
            )
        return normalized


class NsmConfigRulebookSerializer(serializers.Serializer):
    parent_slug = serializers.CharField(required=False, allow_blank=True, default="")
    matrix_tab_enabled = serializers.BooleanField(required=False, default=True)
    row_group_by_col_id = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )


class NsmConfigDocumentSerializer(serializers.Serializer):
    rule_view = NsmConfigRuleViewSerializer(required=False)
    rulebook = NsmConfigRulebookSerializer(required=False)


class NsmConfigApiSerializer(serializers.Serializer):
    slug = serializers.CharField(read_only=True)
    custom_object_type_id = serializers.IntegerField(read_only=True)
    nsm_config = NsmConfigDocumentSerializer()
    comments = serializers.CharField(read_only=True, allow_blank=True)
