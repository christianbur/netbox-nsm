from netbox.api.serializers import NetBoxModelSerializer

from netbox_nsm.models.nsm_type_config import NSMTypeConfig

__all__ = ("NSMTypeConfigSerializer",)


class NSMTypeConfigSerializer(NetBoxModelSerializer):
    """Minimal serializer required so NetBox's changelog/delete signals can
    resolve ``get_serializer_for_model(NSMTypeConfig)``.  No API endpoint
    is registered for this serializer."""

    class Meta:
        model = NSMTypeConfig
        fields = (
            "id",
            "display",
            "content_type",
            "display_template",
            "order_id",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        brief_fields = ("id", "display", "content_type")

