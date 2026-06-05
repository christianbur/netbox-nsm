from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import NetBoxModelSerializer

from netbox_nsm.models import ObjectGroup

__all__ = ("ObjectGroupSerializer",)


class ObjectGroupSerializer(NetBoxModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:objectgroup-detail"
    )

    class Meta:
        model = ObjectGroup
        fields = (
            "id",
            "url",
            "display",
            "name",
            "field_slugs",
            "description",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        brief_fields = ("id", "url", "display", "name")
