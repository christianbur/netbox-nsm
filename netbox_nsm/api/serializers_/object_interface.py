from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import PrimaryModelSerializer

from netbox_nsm.models import ObjectInterface


class ObjectInterfaceSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:objectinterface-detail"
    )

    class Meta:
        model = ObjectInterface
        fields = (
            "id",
            "url",
            "display",
            "name",
            "direction",
            "device",
            "interface",
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
            "direction",
        )
