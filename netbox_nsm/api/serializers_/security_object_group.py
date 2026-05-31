from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import NetBoxModelSerializer

from netbox_nsm.models import SecurityObjectGroup

__all__ = ("SecurityObjectGroupSerializer",)


class SecurityObjectGroupSerializer(NetBoxModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:securityobjectgroup-detail"
    )

    class Meta:
        model = SecurityObjectGroup
        fields = (
            "id",
            "url",
            "display",
            "name",
            "description",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        brief_fields = ("id", "url", "display", "name")
