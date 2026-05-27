from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import PrimaryModelSerializer

from netbox_nsm.models import SecurityObjectType


class SecurityObjectTypeSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:securityobjecttype-detail"
    )

    class Meta:
        model = SecurityObjectType
        fields = (
            "id",
            "url",
            "display",
            "name",
            "area",
            "field_definitions",
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
            "area",
        )
