from rest_framework.serializers import (
    HyperlinkedIdentityField,
    IntegerField,
)
from netbox.api.serializers import PrimaryModelSerializer
from tenancy.api.serializers import TenantSerializer

from netbox_nsm.models import SecurityZone


class SecurityZoneSerializer(PrimaryModelSerializer):
    url = HyperlinkedIdentityField(
        view_name="plugins-api:netbox_nsm-api:securityzone-detail"
    )
    source_policy_count = IntegerField(read_only=True)
    destination_policy_count = IntegerField(read_only=True)
    tenant = TenantSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = SecurityZone
        fields = (
            "id",
            "url",
            "display",
            "name",
            "color",
            "description",
            "tenant",
            "source_policy_count",
            "destination_policy_count",
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
            "name",
            "color",
            "source_policy_count",
            "destination_policy_count",
            "description",
        )

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)


