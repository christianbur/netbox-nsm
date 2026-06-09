from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from netbox.api.serializers import NetBoxModelSerializer
from netbox_nsm.constants import RULESET_ASSIGNMENT_MODELS
from netbox_nsm.models import CotRulebookAssignment

__all__ = ("CotRulebookAssignmentSerializer",)


class CotRulebookAssignmentSerializer(NetBoxModelSerializer):
    assigned_object_type = serializers.SlugRelatedField(
        slug_field="pk",
        queryset=ContentType.objects.filter(RULESET_ASSIGNMENT_MODELS),
    )

    class Meta:
        model = CotRulebookAssignment
        fields = (
            "id",
            "url",
            "display",
            "assigned_object_type",
            "assigned_object_id",
            "cot_slug",
            "description",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
