from django.contrib.contenttypes.models import ContentType
from drf_spectacular.utils import extend_schema_field
from rest_framework.serializers import HyperlinkedIdentityField, SerializerMethodField
from rest_framework.validators import UniqueTogetherValidator
from netbox.api.exceptions import SerializerNotFound
from netbox.api.fields import ContentTypeField
from netbox.api.serializers import NetBoxModelSerializer
from utilities.api import get_serializer_for_model
from utilities.serialization import serialize_object

from netbox_nsm.models import ObjectLink

__all__ = ("ObjectLinkSerializer", "_serialize_linked_object")


def _serialize_linked_object(obj, request):
    """Nested representation for GFK endpoints; tolerate missing API serializers."""
    if obj is None:
        return None
    try:
        serializer = get_serializer_for_model(obj.__class__)
    except SerializerNotFound:
        data = serialize_object(obj)
        data["id"] = obj.pk
        data["display"] = str(obj)
        return data
    context = {"request": request}
    return serializer(obj, nested=True, context=context).data


class ObjectLinkSerializer(NetBoxModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:objectlink-detail"
    )
    object_a_type = ContentTypeField(queryset=ContentType.objects.all())
    object_b_type = ContentTypeField(queryset=ContentType.objects.all())
    object_a = SerializerMethodField(read_only=True)
    object_b = SerializerMethodField(read_only=True)

    class Meta:
        model = ObjectLink
        fields = (
            "id",
            "url",
            "display",
            "object_a_type",
            "object_a_id",
            "object_a",
            "object_b_type",
            "object_b_id",
            "object_b",
            "comment",
            "propagation",
            "propagate_stop_on_own",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        brief_fields = (
            "id",
            "url",
            "display",
            "object_a_type",
            "object_a_id",
            "object_b_type",
            "object_b_id",
        )
        validators = [
            UniqueTogetherValidator(
                queryset=ObjectLink.objects.all(),
                fields=("object_a_type", "object_a_id", "object_b_type", "object_b_id"),
                message="Ein Link zwischen diesen Objekten existiert bereits.",
            )
        ]

    @extend_schema_field({"type": "object"})
    def get_object_a(self, obj):
        return _serialize_linked_object(obj.object_a, self.context.get("request"))

    @extend_schema_field({"type": "object"})
    def get_object_b(self, obj):
        return _serialize_linked_object(obj.object_b, self.context.get("request"))
