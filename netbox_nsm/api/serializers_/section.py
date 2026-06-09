from rest_framework import serializers

from netbox.api.serializers import NetBoxModelSerializer

from netbox_nsm.models import Section

__all__ = ("SectionSerializer",)


class SectionSerializer(NetBoxModelSerializer):
    """REST/changelog serializer for internal NSM section groupings."""

    custom_object_types = serializers.PrimaryKeyRelatedField(
        many=True,
        read_only=True,
    )

    class Meta:
        model = Section
        fields = (
            "id",
            "display",
            "slug",
            "name",
            "sort_order",
            "custom_object_types",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        brief_fields = ("id", "display", "slug", "name")
