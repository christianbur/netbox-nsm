from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import PrimaryModelSerializer

from netbox_nsm.api.serializers_.nsm_object_type import NsmObjectTypeSerializer
from netbox_nsm.models import NsmObject


class NsmObjectSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:nsmobject-detail"
    )
    nsm_object_type = NsmObjectTypeSerializer(nested=True)

    class Meta:
        model = NsmObject
        fields = (
            "id",
            "url",
            "display",
            "nsm_object_type",
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
            "nsm_object_type",
            "name",
        )
