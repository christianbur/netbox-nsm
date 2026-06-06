from rest_framework import serializers
from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.fields import ContentTypeField
from netbox.api.serializers import NetBoxModelSerializer

from netbox_nsm.models import TypeConfig

__all__ = ("TypeConfigSerializer",)


class TypeConfigSerializer(NetBoxModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:typeconfig-detail"
    )
    content_type = ContentTypeField(read_only=True)
    panel_linkable = serializers.BooleanField(required=False)

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
            "allow_virtual_groups",
            "inherit_links",
            "inherit_stop_on_own",
            "panel_linkable",
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
            "inherit_links",
            "panel_linkable",
        )
