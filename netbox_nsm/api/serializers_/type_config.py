from rest_framework.serializers import HyperlinkedIdentityField
from netbox.api.fields import ContentTypeField
from netbox.api.serializers import NetBoxModelSerializer

from netbox_nsm.models.type_config import TypeConfig

__all__ = ("TypeConfigSerializer",)


class TypeConfigSerializer(NetBoxModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:typeconfig-detail"
    )
    content_type = ContentTypeField(read_only=True)

    class Meta:
        model = TypeConfig
        fields = (
            "id",
            "url",
            "display",
            "content_type",
            "matching_class",
            "display_template",
            "allowed_placements",
            "inherit_links",
            "inherit_stop_on_own",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        brief_fields = (
            "id",
            "url",
            "display",
            "content_type",
            "matching_class",
            "inherit_links",
        )
