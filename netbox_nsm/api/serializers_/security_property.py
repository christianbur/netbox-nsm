from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import PrimaryModelSerializer

from netbox_nsm.api.serializers_.security_property_type import SecurityPropertyTypeSerializer
from netbox_nsm.models import SecurityProperty


class SecurityPropertySerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:securityproperty-detail"
    )
    security_property_type = SecurityPropertyTypeSerializer(nested=True)

    class Meta:
        model = SecurityProperty
        fields = (
            "id",
            "url",
            "display",
            "security_property_type",
            "name",
            "object_data",
            "source_model",
            "source_pk",
            "description",
            "comments",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        brief_fields = (
            "id",
            "url",
            "display",
            "security_property_type",
            "name",
        )
