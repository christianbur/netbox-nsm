from rest_framework import serializers
from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.fields import ContentTypeField
from netbox.api.serializers import NetBoxModelSerializer

from netbox_nsm.changelog_utils import apply_type_config_changelog_message
from netbox_nsm.models import TypeConfig

__all__ = ("TypeConfigSerializer",)


class TypeConfigSerializer(NetBoxModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:typeconfig-detail"
    )
    content_type = ContentTypeField(read_only=True)
    panel_linkable_types = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )
    inherit_links = serializers.BooleanField(read_only=True)
    inherit_stop_on_own = serializers.BooleanField(read_only=True)

    class Meta:
        model = TypeConfig
        fields = (
            "id",
            "url",
            "display",
            "name",
            "content_type",
            "matching_class",
            "display_template",
            "panel_slugs",
            "order_id",
            "inherit_links",
            "inherit_stop_on_own",
            "panel_linkable_types",
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
            "content_type",
            "matching_class",
            "panel_slugs",
            "panel_linkable_types",
        )

    def update(self, instance, validated_data):
        prechange = getattr(instance, "_prechange_snapshot", None)
        if prechange and "changelog_message" not in validated_data:
            for attr, value in validated_data.items():
                if attr != "changelog_message":
                    setattr(instance, attr, value)
            apply_type_config_changelog_message(instance, prechange=prechange)
            if instance._changelog_message:
                validated_data = {
                    **validated_data,
                    "changelog_message": instance._changelog_message,
                }
        return super().update(instance, validated_data)
