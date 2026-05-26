from django.contrib.contenttypes.models import ContentType
from rest_framework.serializers import HyperlinkedIdentityField, SerializerMethodField

from netbox.api.fields import ContentTypeField
from netbox.api.serializers import NetBoxModelSerializer

from netbox_nsm.constants import OBJECT_ASSIGNMENT_MODELS
from netbox_nsm.models import ObjectCustomObjectAssignment
from .object_custom_object import ObjectCustomObjectSerializer


class ObjectCustomObjectAssignmentSerializer(NetBoxModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:objectcustomobjectassignment-detail"
    )
    custom_object = ObjectCustomObjectSerializer(nested=True, required=True)
    assigned_object_type = ContentTypeField(
        queryset=ContentType.objects.filter(OBJECT_ASSIGNMENT_MODELS)
    )
    assigned_object = SerializerMethodField(read_only=True)

    def get_assigned_object(self, obj):
        if obj.assigned_object is None:
            return None
        serializer = None
        try:
            from netbox.api.serializers import get_serializer_for_model
            serializer = get_serializer_for_model(obj.assigned_object)
        except Exception:
            return None
        if serializer is None:
            return None
        return serializer(obj.assigned_object, nested=True, context=self.context).data

    class Meta:
        model = ObjectCustomObjectAssignment
        fields = [
            "id",
            "url",
            "display",
            "custom_object",
            "assigned_object_type",
            "assigned_object_id",
            "assigned_object",
            "comment",
            "created",
            "last_updated",
        ]
        brief_fields = (
            "id",
            "url",
            "display",
            "custom_object",
            "assigned_object_type",
            "assigned_object_id",
        )
