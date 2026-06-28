from rest_framework import serializers

from netbox_nsm.core.display_template import (
    DEFAULT_DISPLAY_TEMPLATE,
    normalize_display_template,
    validate_display_template,
)

__all__ = (
    "NsmConfigDocumentSerializer",
    "NsmConfigLinksSerializer",
    "NsmConfigRuleViewSerializer",
    "NsmConfigRulebookSerializer",
)


class NsmConfigRuleViewSerializer(serializers.Serializer):
    sort_order = serializers.IntegerField(min_value=0, required=False, default=0)
    display_template = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default=DEFAULT_DISPLAY_TEMPLATE,
    )

    def validate_display_template(self, value):
        tmpl = normalize_display_template(value)
        validate_display_template(tmpl)
        return tmpl


class NsmConfigRulebookSerializer(serializers.Serializer):
    parent_slug = serializers.CharField(required=False, allow_blank=True, default="")
    matrix_tab_enabled = serializers.BooleanField(required=False, default=True)
    row_group_by_col_id = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )


class NsmConfigLinksSerializer(serializers.Serializer):
    linkable = serializers.BooleanField(required=False, default=True)
    inherit_links = serializers.BooleanField(required=False, default=False)
    inherit_stop_on_own = serializers.BooleanField(required=False, default=False)
    allow_virtual_groups = serializers.BooleanField(required=False, default=False)
    link_table = serializers.CharField(required=False, allow_blank=True, default="")


class NsmConfigDocumentSerializer(serializers.Serializer):
    rule_view = NsmConfigRuleViewSerializer(required=False)
    rulebook = NsmConfigRulebookSerializer(required=False)
    links = NsmConfigLinksSerializer(required=False)


class NsmConfigApiSerializer(serializers.Serializer):
    slug = serializers.CharField(read_only=True)
    custom_object_type_id = serializers.IntegerField(read_only=True)
    nsm_config = NsmConfigDocumentSerializer()
    comments = serializers.CharField(read_only=True, allow_blank=True)
