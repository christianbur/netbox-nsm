from rest_framework import serializers

__all__ = (
    "NsmConfigDocumentSerializer",
    "NsmConfigRuleViewSerializer",
    "NsmConfigRulebookSerializer",
)


class NsmConfigRuleViewSerializer(serializers.Serializer):
    sort_order = serializers.IntegerField(min_value=0, required=False, default=0)
    display_template = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default="{name}",
    )


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
    object_builder = serializers.DictField(required=False)
    rulebook = NsmConfigRulebookSerializer(required=False)


class NsmConfigApiSerializer(serializers.Serializer):
    slug = serializers.CharField(read_only=True)
    custom_object_type_id = serializers.IntegerField(read_only=True)
    nsm_config = NsmConfigDocumentSerializer()
    comments = serializers.CharField(read_only=True, allow_blank=True)
