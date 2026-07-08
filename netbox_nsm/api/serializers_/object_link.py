from django.contrib.contenttypes.models import ContentType
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.reverse import reverse

from netbox.api.exceptions import SerializerNotFound
from netbox.api.fields import ContentTypeField
from utilities.api import get_serializer_for_model
from utilities.serialization import serialize_object

from netbox_nsm.security.links.object_link_service import (
    ObjectLinkRecord,
    create_or_update_links,
    get_object_link_model,
)

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


class ObjectLinkSerializer(serializers.Serializer):
    """REST serializer for COT ``nsm_object_link`` (legacy field names preserved)."""

    id = serializers.IntegerField(read_only=True)
    url = serializers.SerializerMethodField()
    display = serializers.SerializerMethodField()
    object_a_type = ContentTypeField(queryset=ContentType.objects.all(), required=False)
    object_a_id = serializers.IntegerField(required=False)
    object_a = serializers.SerializerMethodField(read_only=True)
    object_b_type = ContentTypeField(queryset=ContentType.objects.all(), required=False)
    object_b_id = serializers.IntegerField(required=False)
    object_b = serializers.SerializerMethodField(read_only=True)
    comment = serializers.CharField(required=False, allow_blank=True, default="")
    created = serializers.DateTimeField(read_only=True)
    last_updated = serializers.DateTimeField(read_only=True)

    def _record(self, instance) -> ObjectLinkRecord:
        if isinstance(instance, ObjectLinkRecord):
            return instance
        return ObjectLinkRecord.from_instance(instance)

    def get_url(self, obj):
        request = self.context.get("request")
        record = self._record(obj)
        return reverse(
            "plugins-api:netbox_nsm-api:objectlink-detail",
            kwargs={"pk": record.pk},
            request=request,
        )

    def get_display(self, obj):
        return str(self._record(obj))

    @extend_schema_field({"type": "object"})
    def get_object_a(self, obj):
        record = self._record(obj)
        return _serialize_linked_object(record.netbox_object, self.context.get("request"))

    @extend_schema_field({"type": "object"})
    def get_object_b(self, obj):
        record = self._record(obj)
        return _serialize_linked_object(record.security_object, self.context.get("request"))

    def to_representation(self, instance):
        record = self._record(instance)
        cot = record.instance
        return {
            "id": record.pk,
            "url": self.get_url(cot),
            "display": str(record),
            "object_a_type": record.object_a_type.pk if record.object_a_type else None,
            "object_a_id": record.object_a_id,
            "object_a": self.get_object_a(cot),
            "object_b_type": record.object_b_type.pk if record.object_b_type else None,
            "object_b_id": record.object_b_id,
            "object_b": self.get_object_b(cot),
            "comment": record.comment,
            "created": getattr(cot, "created", None),
            "last_updated": getattr(cot, "last_updated", None),
        }

    def create(self, validated_data):
        a_type = validated_data.pop("object_a_type")
        a_id = validated_data.pop("object_a_id")
        b_type = validated_data.pop("object_b_type")
        b_id = validated_data.pop("object_b_id")
        object_a = a_type.get_object_for_this_type(pk=a_id)
        object_b = b_type.get_object_for_this_type(pk=b_id)
        record, _created = create_or_update_links(
            object_a,
            object_b,
            comment=validated_data.get("comment", ""),
        )
        return record.instance

    def update(self, instance, validated_data):
        record = self._record(instance)
        updated = create_or_update_links(
            record.netbox_object,
            record.security_object,
            comment=validated_data.get("comment", record.comment),
        )[0]
        return updated.instance

    def validate(self, data):
        if self.instance is not None:
            return data
        required = ("object_a_type", "object_a_id", "object_b_type", "object_b_id")
        missing = [field for field in required if data.get(field) in (None, "")]
        if missing:
            raise serializers.ValidationError(
                {field: "This field is required." for field in missing}
            )
        model = get_object_link_model()
        if model is None:
            raise serializers.ValidationError("COT nsm_object_link is not deployed.")
        filt = {
            "netbox_object_content_type": data["object_a_type"],
            "netbox_object_object_id": data["object_a_id"],
            "security_object_content_type": data["object_b_type"],
            "security_object_object_id": data["object_b_id"],
        }
        if model.objects.filter(**filt).exists():
            raise serializers.ValidationError(
                "Ein Link zwischen diesen Objekten existiert bereits."
            )
        return data
