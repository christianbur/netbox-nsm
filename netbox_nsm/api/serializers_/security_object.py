from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import PrimaryModelSerializer
from netbox.api.fields import SerializedPKRelatedField

from netbox_nsm.models import SecurityObject, SecurityObjectType
from .security_object_type import SecurityObjectTypeSerializer


class SecurityObjectSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:securityobject-detail"
    )
    custom_type = SecurityObjectTypeSerializer(nested=True)

    class Meta:
        model = SecurityObject
        fields = (
            "id",
            "url",
            "display",
            "custom_type",
            "name",
            "description",
            "field_data",
            "table_data",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        brief_fields = (
            "id",
            "url",
            "display",
            "custom_type",
            "name",
        )
