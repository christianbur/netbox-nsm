from rest_framework.serializers import HyperlinkedIdentityField

from netbox.api.serializers import PrimaryModelSerializer
from netbox.api.fields import SerializedPKRelatedField

from netbox_nsm.models import ObjectCustomObject, ObjectCustomType
from .object_custom_type import ObjectCustomTypeSerializer


class ObjectCustomObjectSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:objectcustomobject-detail"
    )
    custom_type = ObjectCustomTypeSerializer(nested=True)

    class Meta:
        model = ObjectCustomObject
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
