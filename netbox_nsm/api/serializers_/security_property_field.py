from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import PrimaryModelSerializer

from netbox_nsm.api.serializers_.security_property_type import SecurityPropertyTypeSerializer
from netbox_nsm.models import SecurityPropertyField


class SecurityPropertyFieldSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:securitypropertyfield-detail"
    )
    security_property_type = SecurityPropertyTypeSerializer(nested=True)

    class Meta:
        model = SecurityPropertyField
        fields = (
            "id",
            "url",
            "display",
            "security_property_type",
            "name",
            "label",
            "type",
            "group_name",
            "required",
            "unique",
            "default",
            "weight",
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
            "type",
        )
